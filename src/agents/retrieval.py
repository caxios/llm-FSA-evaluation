"""Retrieval for structure R (P9 §5.2, D9.1, D9.2).

Chunking (D9.2, adapted to the rendered package): one chunk per top-level block ("[...]"
headers) and per table ("<...>" titles); long tables are split into windows of
`WINDOW_ROWS` rows that repeat the table title and header row, which approximates the
current / non-current sections of the statements.

Embeddings (D9.1, revised): Gemini `gemini-embedding-001` through the OpenAI-compatible
endpoint instead of a local model (the machine has 8 GB of memory; a local BGE-M3 does not
fit next to the runner). Vectors are cached by text hash in results/cache/embeddings.sqlite.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config import PROJECT_ROOT, require_env

EMBED_MODEL = "gemini-embedding-001"
EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/openai/embeddings"
CACHE = PROJECT_ROOT / "results" / "cache" / "embeddings.sqlite"
WINDOW_ROWS = 25
CHUNKING = "v1"


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str


def chunk_prompt(text: str) -> list[Chunk]:
    """Split a rendered user prompt into retrieval chunks (ids are stable: c00, c01, ...)."""
    blocks: list[list[str]] = []
    for line in text.split("\n"):
        if line.startswith("[") or line.startswith("<") or not blocks:
            blocks.append([line])
        else:
            blocks[-1].append(line)
    pieces: list[str] = []
    for b in blocks:
        while b and not b[-1].strip():
            b = b[:-1]
        if not b:
            continue
        is_row = [ln.startswith("| ") and not ln.startswith("| 계정") for ln in b]
        rows = [ln for ln, r in zip(b, is_row, strict=True) if r]
        if len(rows) > WINDOW_ROWS:
            head = [ln for ln, r in zip(b, is_row, strict=True) if not r]
            for i in range(0, len(rows), WINDOW_ROWS):
                pieces.append("\n".join(head + rows[i:i + WINDOW_ROWS]))
        else:
            pieces.append("\n".join(b))
    # a top-level header line alone ("[재무제표] ...") is merged into the next chunk
    merged: list[str] = []
    carry = ""
    for p in pieces:
        if "\n" not in p and p.startswith("["):
            carry = p + "\n"
            continue
        merged.append(carry + p)
        carry = ""
    if carry:
        merged.append(carry.strip())
    return [Chunk(f"c{i:02d}", t) for i, t in enumerate(merged)]


class Embedder:
    """Embeddings with a persistent cache (thread-safe)."""

    def __init__(self, cache_path: Path = CACHE, session: requests.Session | None = None,
                 model: str = EMBED_MODEL):
        self.model = model
        self.session = session or requests.Session()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(cache_path, check_same_thread=False)
        self.conn.execute("CREATE TABLE IF NOT EXISTS emb (sha TEXT PRIMARY KEY, model TEXT, "
                          "vec BLOB)")
        self.lock = threading.Lock()
        self._key: str | None = None

    @staticmethod
    def _sha(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @retry(retry=retry_if_exception_type(requests.RequestException),
           wait=wait_exponential(min=2, max=60), stop=stop_after_attempt(8), reraise=True)
    def _fetch(self, texts: list[str]) -> list[np.ndarray]:
        self._key = self._key or require_env("GOOGLE_API_KEY")
        r = self.session.post(EMBED_URL, json={"model": self.model, "input": texts},
                              headers={"Authorization": f"Bearer {self._key}"}, timeout=120)
        if r.status_code == 429 or r.status_code >= 500:
            raise requests.RequestException(f"HTTP {r.status_code}")
        r.raise_for_status()
        data = r.json()["data"]   # Gemini's endpoint omits "index"; order follows the input
        if all("index" in d for d in data):
            data = sorted(data, key=lambda d: d["index"])
        if len(data) != len(texts):
            raise requests.RequestException(f"{len(data)} embeddings for {len(texts)} texts")
        return [np.asarray(d["embedding"], dtype=np.float32) for d in data]

    def embed(self, texts: list[str]) -> np.ndarray:
        shas = [self._sha(t) for t in texts]
        found: dict[str, np.ndarray] = {}
        with self.lock:
            for s in set(shas):
                row = self.conn.execute("SELECT vec FROM emb WHERE sha = ? AND model = ?",
                                        (s, self.model)).fetchone()
                if row:
                    found[s] = np.frombuffer(row[0], dtype=np.float32)
        missing = [(s, t) for s, t in dict(zip(shas, texts, strict=True)).items()
                   if s not in found]
        for i in range(0, len(missing), 50):
            part = missing[i:i + 50]
            vecs = self._fetch([t for _, t in part])
            with self.lock:
                for (s, _), v in zip(part, vecs, strict=True):
                    self.conn.execute("INSERT OR REPLACE INTO emb VALUES (?, ?, ?)",
                                      (s, self.model, v.tobytes()))
                    found[s] = v
                self.conn.commit()
        return np.vstack([found[s] for s in shas])


class Retriever:
    def __init__(self, embedder, chunks: list[Chunk]):
        self.chunks = chunks
        m = embedder.embed([c.text for c in chunks])
        self.matrix = m / np.linalg.norm(m, axis=1, keepdims=True)
        self.embedder = embedder

    def top_k(self, query: str, k: int = 4) -> list[Chunk]:
        q = self.embedder.embed([query])[0]
        q = q / np.linalg.norm(q)
        order = np.argsort(-(self.matrix @ q), kind="stable")[:k]
        return [self.chunks[i] for i in order]
