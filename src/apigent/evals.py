"""Measure answer quality on a fixed set of questions before shipping.

eval file (YAML)::

    cases:
      - question: "Phòng Kế toán có bao nhiêu nhân viên?"
        token: "Bearer manager-token"
        expect_contains: ["8"]
        expect_tools: ["getHeadcount"]
        expect_not_contains: ["lương"]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from apigent.agent import Agent, AgentResult
from apigent.context import UserContext


@dataclass
class EvalCase:
    question: str
    token: str | None = None
    roles: list[str] = field(default_factory=list)
    expect_contains: list[str] = field(default_factory=list)
    expect_not_contains: list[str] = field(default_factory=list)
    expect_tools: list[str] = field(default_factory=list)


@dataclass
class EvalOutcome:
    case: EvalCase
    result: AgentResult | None
    passed: bool
    reasons: list[str]


def load_cases(path: str | Path) -> list[EvalCase]:
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return [EvalCase(**c) for c in data.get("cases", [])]


def check(case: EvalCase, res: AgentResult) -> list[str]:
    reasons: list[str] = []
    answer = res.answer.lower()
    for s in case.expect_contains:
        if s.lower() not in answer:
            reasons.append(f"missing {s!r}")
    for s in case.expect_not_contains:
        if s.lower() in answer:
            reasons.append(f"should not contain {s!r}")
    called = {s.name for s in res.steps}
    for t in case.expect_tools:
        if t not in called:
            reasons.append(f"tool {t} not called")
    return reasons


async def run_eval(agent: Agent, cases: list[EvalCase]) -> list[EvalOutcome]:
    outcomes: list[EvalOutcome] = []
    for case in cases:
        ctx = UserContext(auth_token=case.token, roles=tuple(case.roles))
        try:
            res = await agent.ask(case.question, ctx=ctx)
        except Exception as e:  # noqa: BLE001
            outcomes.append(EvalOutcome(case, None, False, [f"error: {e}"]))
            continue
        reasons = check(case, res)
        outcomes.append(EvalOutcome(case, res, not reasons, reasons))
    return outcomes


def summarise(outcomes: list[EvalOutcome]) -> str:
    lines = []
    for o in outcomes:
        mark = "PASS" if o.passed else "FAIL"
        lines.append(f"[{mark}] {o.case.question}")
        if not o.passed:
            lines.append(f"       {'; '.join(o.reasons)}")
            if o.result:
                lines.append(f"       answer: {o.result.answer[:200]}")
    passed = sum(o.passed for o in outcomes)
    total = len(outcomes) or 1
    lines.append(f"\n{passed}/{len(outcomes)} passed ({passed / total:.0%})")
    return "\n".join(lines)
