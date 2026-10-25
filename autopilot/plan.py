"""Plan contract: dataclasses, JSON load/save, schema-level validation."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

TARGET_STATES = ("proven", "unreasonable on purpose", "guess")
SCOPE_POLICIES = ("fail", "report")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
DEFAULT_TOOLS = [
    "Read", "Edit", "Write", "Glob", "Grep",
    "Bash(python3:*)", "Bash(git add:*)", "Bash(git commit:*)",
    "Bash(git diff:*)", "Bash(git status:*)", "Bash(git log:*)",
]


@dataclass
class Judge:
    cmd: str
    paths: list[str]
    pass_rule: str = "exit 0"          # JSON key "pass"; only "exit 0" is implemented
    sha256: dict[str, str] = field(default_factory=dict)
    timeout_s: int = 600
    canary: dict[str, str] | None = None   # {path, content}: a test file the judge must FAIL on


@dataclass
class Target:
    value: str = ""
    state: str = "guess (no baseline)"


@dataclass
class Item:
    id: str
    goal: str
    scope: list[str]
    judge: Judge
    target: Target = field(default_factory=Target)
    stop_line: int = 3
    interfaces: str = ""
    notes: str = ""


@dataclass
class Global:
    max_cost_usd: float = 20.0
    max_wall_minutes: float = 180
    max_attempts_total: int = 30
    no_progress_limit: int = 2
    scope_policy: str = "fail"         # fail | report
    strict_receipts: bool = False      # True: a fake receipt fails the attempt
    model: str = "claude-sonnet-5-5"
    max_turns: int = 60
    max_budget_usd_per_attempt: float = 2.0
    attempt_timeout_s: int = 1800
    allowed_tools: list[str] = field(default_factory=lambda: list(DEFAULT_TOOLS))
    constraints: str = ""


@dataclass
class Plan:
    plan_id: str
    base_sha: str
    items: list[Item]
    glob: Global = field(default_factory=Global)   # JSON key "global"
    contract_ref: str = ""
    task: str = ""
    next_rung: str = ""

    def __post_init__(self) -> None:
        if not self.contract_ref:
            self.contract_ref = f"refs/contract/{self.plan_id}"

    def item(self, item_id: str) -> Item:
        for it in self.items:
            if it.id == item_id:
                return it
        raise KeyError(item_id)


def _judge_from(d: dict[str, Any]) -> Judge:
    return Judge(cmd=str(d.get("cmd", "")), paths=list(d.get("paths", [])),
                 pass_rule=str(d.get("pass", "exit 0")), sha256=dict(d.get("sha256", {})),
                 timeout_s=int(d.get("timeout_s", 600)), canary=d.get("canary") or None)


def _item_from(d: dict[str, Any]) -> Item:
    t = d.get("target") or {}
    return Item(id=str(d.get("id", "")), goal=str(d.get("goal", "")), scope=list(d.get("scope", [])),
                judge=_judge_from(d.get("judge") or {}),
                target=Target(value=str(t.get("value", "")), state=str(t.get("state", "guess (no baseline)"))),
                stop_line=int(d.get("stop_line", 3)), interfaces=str(d.get("interfaces", "")),
                notes=str(d.get("notes", "")))


def from_dict(d: dict[str, Any]) -> Plan:
    g = d.get("global") or {}
    glob = Global(**{k: v for k, v in g.items() if k in Global.__dataclass_fields__})
    return Plan(plan_id=str(d.get("plan_id", "")), base_sha=str(d.get("base_sha", "")),
                items=[_item_from(x) for x in d.get("items", [])], glob=glob,
                contract_ref=str(d.get("contract_ref", "")), task=str(d.get("task", "")),
                next_rung=str(d.get("next_rung", "")))


def to_dict(plan: Plan) -> dict[str, Any]:
    items = []
    for it in plan.items:
        d = asdict(it)
        j = d.pop("judge")
        j["pass"] = j.pop("pass_rule")
        d["judge"] = j
        items.append(d)
    return {"plan_id": plan.plan_id, "task": plan.task, "base_sha": plan.base_sha,
            "contract_ref": plan.contract_ref, "global": asdict(plan.glob), "items": items,
            "next_rung": plan.next_rung}


def load(path: str | Path) -> Plan:
    return from_dict(json.loads(Path(path).read_text()))


def dumps(plan: Plan) -> str:
    return json.dumps(to_dict(plan), indent=2, sort_keys=False) + "\n"


def save(plan: Plan, path: str | Path) -> None:
    Path(path).write_text(dumps(plan))


def validate(plan: Plan) -> list[str]:
    """Schema-level problems. Git-level checks live in lint.py."""
    p: list[str] = []
    if not ID_RE.match(plan.plan_id or ""):
        p.append(f"plan_id {plan.plan_id!r} must match {ID_RE.pattern}")
    if not plan.items:
        p.append("plan has no items")
    seen: set[str] = set()
    for it in plan.items:
        tag = f"item {it.id or '?'}"
        if not ID_RE.match(it.id or ""):
            p.append(f"{tag}: id must match {ID_RE.pattern}")
        if it.id in seen:
            p.append(f"{tag}: duplicate id")
        seen.add(it.id)
        if not it.goal.strip():
            p.append(f"{tag}: goal is empty")
        if not it.scope or not all(isinstance(s, str) and s.strip() for s in it.scope):
            p.append(f"{tag}: scope must be a non-empty list of paths")
        if not it.judge.cmd.strip():
            p.append(f"{tag}: judge.cmd is empty")
        if not it.judge.paths or not all(isinstance(s, str) and s.strip() for s in it.judge.paths):
            p.append(f"{tag}: judge.paths must be a non-empty list of paths")
        if it.judge.pass_rule.strip() != "exit 0":
            p.append(f"{tag}: judge.pass {it.judge.pass_rule!r} unsupported (only 'exit 0')")
        if it.stop_line < 1:
            p.append(f"{tag}: stop_line must be >= 1")
        if not it.target.state.startswith(TARGET_STATES):
            p.append(f"{tag}: target.state must start with one of {TARGET_STATES}")
        if it.judge.timeout_s <= 0:
            p.append(f"{tag}: judge.timeout_s must be > 0")
    g = plan.glob
    if g.scope_policy not in SCOPE_POLICIES:
        p.append(f"global.scope_policy must be one of {SCOPE_POLICIES}")
    for name in ("max_cost_usd", "max_wall_minutes", "max_attempts_total", "no_progress_limit",
                 "max_turns", "max_budget_usd_per_attempt", "attempt_timeout_s"):
        if getattr(g, name) <= 0:
            p.append(f"global.{name} must be > 0")
    if not g.allowed_tools:
        p.append("global.allowed_tools is empty")
    return p
