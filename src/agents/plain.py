"""Plain agent (structure P): one call with the full package, validated with retries."""

from __future__ import annotations

from src.agents.base import RunRecord, RunRequest, make_record
from src.agents.llm_client import LLMClient, decoding
from src.config import ModelConfig
from src.data.package_schema import InputPackage
from src.parse.schema import SCHEMAS
from src.parse.validate import run_with_retries


class PlainAgent:
    structure = "P"

    def __init__(self, client: LLMClient, cfg: ModelConfig, max_retries: int = 2):
        self.client, self.cfg, self.max_retries = client, cfg, max_retries

    def identity(self) -> dict:
        return {"model_id": self.cfg.model_id, "decoding": decoding(self.cfg)}

    def run(self, req: RunRequest, package: InputPackage | None = None) -> RunRecord:
        out, raws, err = run_with_retries(self.client, req.messages, self.cfg,
                                          SCHEMAS[req.schema_name], self.max_retries)
        return make_record(req, self.identity(), valid=out is not None,
                           output=out.model_dump(mode="json") if out else None, raws=raws,
                           error=err)
