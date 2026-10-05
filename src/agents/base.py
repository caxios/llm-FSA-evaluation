"""Run request / record types and the agent protocol (P5 §5.4).

Every agent — LLM-based (P, T) or synthetic (SYN) — takes a fully rendered `RunRequest`
(plus the package it was rendered from, which synthetic agents read) and returns a
`RunRecord`. The cache key (D5.3) hashes the rendered messages, the agent identity (model
id and decoding, or synthetic agent parameters), the rep, the agent structure and the
schema version; the experiment name is not part of it, so identical prompts requested by
different experiments share one call.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from functools import lru_cache
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from src.agents.llm_client import RawResponse
from src.config import PROJECT_ROOT
from src.data.package_schema import InputPackage
from src.parse.schema import SCHEMA_VERSION
from src.perturb.base import PerturbMeta
from src.utils.hashing import stable_hash

AgentStructure = Literal["P", "T", "R", "SYN"]
SchemaName = Literal["valuation", "identification", "quiz"]


class RunRequest(BaseModel):
    job_id: str
    firm_id: str
    group: str
    experiment: str
    condition: Literal["A", "B", "D", "C"]
    perturbation: PerturbMeta
    agent_structure: AgentStructure
    model_key: str
    prompt_version: str
    prompt_sha: str = ""
    rep: int
    messages: list[dict]
    package_hash: str = ""
    schema_name: SchemaName = "valuation"
    tag: str = ""


class RunRecord(BaseModel):
    request: RunRequest
    cache_key: str
    attempts: int
    valid: bool
    error: str | None = None
    output: dict[str, Any] | None = None
    raw: list[RawResponse] = Field(default_factory=list)
    model_reported: str = ""
    code_version: str = ""
    finished_at: datetime


class Agent(Protocol):
    structure: AgentStructure

    def identity(self) -> dict: ...

    def run(self, req: RunRequest, package: InputPackage | None = None) -> RunRecord: ...


def cache_key(req: RunRequest, identity: dict) -> str:
    return stable_hash({"messages": req.messages, "agent": identity, "rep": req.rep,
                        "structure": req.agent_structure, "schema": req.schema_name,
                        "schema_version": SCHEMA_VERSION})


@lru_cache(maxsize=1)
def code_version() -> str:
    """Current git commit, suffixed with '-dirty' when tracked files have changes."""
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                               cwd=PROJECT_ROOT, capture_output=True, text=True,
                               check=True).stdout.strip()
        return head + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def make_record(req: RunRequest, identity: dict, *, valid: bool, output: dict | None,
                raws: list[RawResponse], error: str | None, model_reported: str = ""
                ) -> RunRecord:
    return RunRecord(request=req, cache_key=cache_key(req, identity),
                     attempts=max(len(raws), 1), valid=valid, error=error, output=output,
                     raw=raws, model_reported=model_reported or (raws[-1].model_reported
                                                                 if raws else ""),
                     code_version=code_version(), finished_at=datetime.now())
