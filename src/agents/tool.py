"""Tool agent (structure T, D5.2): one structured call for extraction, assumptions,
yearly FCFF inputs and the dilution decision; Python computes the valuation.

Identification and quiz requests have no tool step and run like the plain agent.
"""

from __future__ import annotations

from src.agents.base import RunRecord, RunRequest, make_record
from src.agents.llm_client import LLMClient, decoding
from src.agents.valuation_tools import value_from_inputs
from src.config import ModelConfig
from src.data.package_schema import InputPackage
from src.parse.schema import SCHEMAS, ToolInputs
from src.parse.validate import run_with_retries


class ToolAgent:
    structure = "T"

    def __init__(self, client: LLMClient, cfg: ModelConfig, max_retries: int = 2):
        self.client, self.cfg, self.max_retries = client, cfg, max_retries

    def identity(self) -> dict:
        return {"model_id": self.cfg.model_id, "decoding": decoding(self.cfg), "tool": "v1"}

    def run(self, req: RunRequest, package: InputPackage | None = None) -> RunRecord:
        schema = ToolInputs if req.schema_name == "valuation" else SCHEMAS[req.schema_name]
        out, raws, err = run_with_retries(self.client, req.messages, self.cfg, schema,
                                          self.max_retries)
        result = None
        if out is not None and isinstance(out, ToolInputs):
            try:
                result = value_from_inputs(out).model_dump(mode="json")
                result["tool_inputs"] = out.model_dump(mode="json")
            except (ValueError, ZeroDivisionError) as e:
                err = f"tool: {e}"
        elif out is not None:
            result = out.model_dump(mode="json")
        return make_record(req, self.identity(), valid=result is not None, output=result,
                           raws=raws, error=None if result is not None else err)
