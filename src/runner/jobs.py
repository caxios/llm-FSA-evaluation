"""Job specifications and their expansion into rendered run requests (P5 §5.7).

A `JobSpec` names firms x conditions x perturbations x reps for one agent and model.
`expand` applies each perturbation (P3), builds the information condition (P4), renders
the messages once per cell and yields one `RunRequest` per rep together with the package it
was rendered from (synthetic agents read it). Infeasible perturbations (out of range, not
applicable) are skipped and reported in `ExpandStats.skipped`.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

from pydantic import BaseModel

from src.agents.base import AgentStructure, RunRequest, SchemaName
from src.agents.prompts.registry import SYSTEM_FOR_VERSION, get_prompt
from src.conditions.build import ConditionedPackage
from src.data.package_schema import InputPackage
from src.perturb import PerturbationError, PerturbMeta, perturb, without_cb
from src.utils.hashing import stable_hash

Perturbations = list[tuple[str, dict]]


class JobSpec(BaseModel):
    experiment: str
    firm_ids: list[str]
    conditions: list[str]
    perturbations: Perturbations | dict[str, Perturbations]
    reps: int | dict[str, int]
    agent_structure: AgentStructure = "P"
    model_key: str = "primary"
    prompt_version: str = "v1"
    schema_name: SchemaName = "valuation"
    include_cb: bool = False
    tag: str = ""

    def perturbations_for(self, firm_id: str) -> Perturbations:
        if isinstance(self.perturbations, dict):
            return self.perturbations.get(firm_id, [])
        return self.perturbations

    def reps_for(self, firm_id: str) -> int:
        return self.reps.get(firm_id, 0) if isinstance(self.reps, dict) else self.reps


class PackageStore(Protocol):
    def package(self, firm_id: str) -> InputPackage: ...

    def group(self, firm_id: str) -> str: ...

    def condition(self, pkg: InputPackage, condition: str) -> ConditionedPackage: ...

    def real_name(self, firm_id: str) -> str: ...

    def eval_date(self) -> date: ...


class SampleStore:
    """The 150 sample packages with their P4 identifiers, fake names and labels."""

    def __init__(self):
        from src.conditions import pipeline as pl

        self.pl = pl
        self.sample = pl.load_sample().set_index("firm_id")
        self._pkgs: dict[str, InputPackage] = {}

    def package(self, firm_id: str) -> InputPackage:
        if firm_id not in self._pkgs:
            self._pkgs[firm_id] = self.pl.load_package(firm_id)
        return self._pkgs[firm_id]

    def group(self, firm_id: str) -> str:
        return str(self.sample.loc[firm_id, "group"])

    def condition(self, pkg: InputPackage, condition: str) -> ConditionedPackage:
        from src.conditions.build import make_condition

        fid = pkg.meta.firm_id
        return make_condition(
            pkg, condition, self.pl.load_identifiers(fid),  # type: ignore[arg-type]
            fake_name=self.pl.fake_names().get(fid) if condition == "D" else None,
            industry_label=self.pl.industry_label((pkg.meta.ksic or "")[:2] or None))

    def real_name(self, firm_id: str) -> str:
        return self.package(firm_id).meta.real_name

    def eval_date(self) -> date:
        return next(iter(self._pkgs.values())).meta.eval_date if self._pkgs else \
            self.package(self.sample.index[0]).meta.eval_date


@dataclass
class ExpandStats:
    requests: int = 0
    cells: int = 0
    skipped: list[tuple[str, str, str]] = field(default_factory=list)


def system_prompt(agent_structure: str, prompt_version: str) -> tuple[str, str]:
    if agent_structure == "T":
        return get_prompt("tool_system_v1")
    return get_prompt(SYSTEM_FOR_VERSION[prompt_version])


def build_messages(spec: JobSpec, cp: ConditionedPackage | None, store: PackageStore,
                   firm_id: str) -> tuple[list[dict], str]:
    """(messages, prompt sha) for one cell."""
    if spec.schema_name == "valuation":
        assert cp is not None
        text, sha = system_prompt(spec.agent_structure, spec.prompt_version)
        user_sha = get_prompt("valuation_user_v1")[1]
        return ([{"role": "system", "content": text},
                 {"role": "user", "content": cp.render(include_cb=spec.include_cb)}],
                stable_hash([sha, user_sha])[:16])
    if spec.schema_name == "identification":
        assert cp is not None
        text, sha = get_prompt("identification_v1")
        return [{"role": "user", "content": text.replace("{package}", cp.render())}], sha[:16]
    text, sha = get_prompt("memory_quiz_v1")
    as_of = store.eval_date()
    content = text.format(name=store.real_name(firm_id),
                          as_of=f"{as_of.year}년 {as_of.month}월 {as_of.day}일",
                          prior_year=as_of.year - 1)
    return [{"role": "user", "content": content}], sha[:16]


def _job_id(spec: JobSpec, firm_id: str, cond: str, name: str, params: dict, rep: int) -> str:
    p = ",".join(f"{k}={v}" for k, v in sorted(params.items()))
    return (f"{spec.experiment}|{firm_id}|{cond}|{name}({p})|{spec.agent_structure}|"
            f"{spec.model_key}|{spec.prompt_version}|r{rep}")


def expand(spec: JobSpec, store: PackageStore, stats: ExpandStats | None = None
           ) -> Iterator[tuple[RunRequest, InputPackage | None]]:
    stats = stats if stats is not None else ExpandStats()
    for firm_id in spec.firm_ids:
        reps = spec.reps_for(firm_id)
        if reps <= 0:
            continue
        group = store.group(firm_id)
        if spec.schema_name == "quiz":
            msgs, sha = build_messages(spec, None, store, firm_id)
            stats.cells += 1
            for rep in range(reps):
                stats.requests += 1
                yield RunRequest(
                    job_id=_job_id(spec, firm_id, "C", "none", {}, rep), firm_id=firm_id,
                    group=group, experiment=spec.experiment, condition="C",
                    perturbation=PerturbMeta(type="none"), agent_structure=spec.agent_structure,
                    model_key=spec.model_key, prompt_version=spec.prompt_version,
                    prompt_sha=sha, rep=rep, messages=msgs, schema_name="quiz",
                    tag=spec.tag), None
            continue
        base = store.package(firm_id)
        if not spec.include_cb:
            base = without_cb(base)
        for name, params in spec.perturbations_for(firm_id):
            if name == "none":
                pkg, meta = base, PerturbMeta(type="none")
            else:
                try:
                    pkg, meta = perturb(base, name, **params)
                except PerturbationError as e:
                    stats.skipped.append((firm_id, f"{name}{params}", str(e)))
                    continue
            for cond in spec.conditions:
                cp = store.condition(pkg, cond)
                msgs, sha = build_messages(spec, cp, store, firm_id)
                stats.cells += 1
                phash = pkg.package_hash()
                for rep in range(reps):
                    stats.requests += 1
                    yield RunRequest(
                        job_id=_job_id(spec, firm_id, cond, name, params, rep),
                        firm_id=firm_id, group=group, experiment=spec.experiment,
                        condition=cond, perturbation=meta,  # type: ignore[arg-type]
                        agent_structure=spec.agent_structure, model_key=spec.model_key,
                        prompt_version=spec.prompt_version, prompt_sha=sha, rep=rep,
                        messages=msgs, package_hash=phash, schema_name=spec.schema_name,
                        tag=spec.tag), cp.package
