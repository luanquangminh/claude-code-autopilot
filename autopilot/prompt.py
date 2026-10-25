"""Per-item brief, the contract system prompt, and the structured self-report schema."""
from __future__ import annotations

from typing import Any

from .plan import Item, Plan

BLOCKER_KINDS = ["none", "impossible_target", "judge_contradicts_spec", "needs_access",
                 "scope_too_small", "other"]

REPORT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["claimed_status", "commands_run", "files_changed", "miss"],
    "properties": {
        "claimed_status": {"type": "string", "enum": ["green", "miss"]},
        "commands_run": {"type": "array", "items": {"type": "string"},
                         "description": "Every shell command you actually ran, verbatim."},
        "files_changed": {"type": "array", "items": {"type": "string"}},
        "miss": {
            "type": "object",
            "required": ["attempt", "gap", "blocker", "blocker_kind"],
            "properties": {
                "attempt": {"type": "string", "description": "Smallest real attempt, with pasted output. Empty when green."},
                "gap": {"type": "string", "description": "Measured gap to the target. Empty when green."},
                "blocker": {"type": "string", "description": "Named blocker. Empty when green."},
                "blocker_kind": {"type": "string", "enum": BLOCKER_KINDS},
            },
        },
    },
}

SYSTEM_RULES = """You are one implementation session inside an automated pipeline. The contract for your item is locked and will be judged by code after you stop, on the COMMITTED state of this worktree.

Rules:
- Never change the judge: do not edit, delete, rename, or special-case the judge command, its files, its data, or the target. If the judge contradicts the spec, stop, commit nothing that touches it, and report the miss with blocker_kind "judge_contradicts_spec". A human decides.
- Change only files inside SCOPE. Anything else is discarded and counts against you.
- Run the judge yourself before you stop. Commit on green with a message that starts with the item id. Uncommitted work is not judged.
- If you cannot reach the target, stop and report the miss honestly: the smallest real attempt with its pasted output, the measured gap, and the named blocker. That is a good result. Do not fake success.
- Your final answer must fill the JSON schema you were given. Every command in commands_run must be one you actually ran; the orchestrator checks the transcript."""


def _tail(s: str, n: int = 40) -> str:
    lines = s.splitlines()
    return "\n".join(lines[-n:])


def build_brief(plan: Plan, item: Item, attempts: list[dict[str, Any]]) -> str:
    lines = [
        "You are implementing ONE item of an approved plan. The contract is locked.",
        "",
        f"ITEM {item.id}: {item.goal}",
        "SCOPE (only these files may change): " + ", ".join(item.scope),
        "JUDGE (do not change this check, its files, or its data):",
        f"  {item.judge.cmd}   -> pass = {item.judge.pass_rule}",
        "  judge files: " + ", ".join(item.judge.paths),
        f"TARGET: {item.target.value} ({item.target.state})",
        f"STOP LINE: {item.stop_line} attempts in total; this is attempt {len(attempts) + 1}.",
    ]
    if item.interfaces:
        lines.append(f"INTERFACES: {item.interfaces}")
    if item.notes:
        lines.append(f"NOTES: {item.notes}")
    if plan.glob.constraints:
        lines += ["GLOBAL CONSTRAINTS:", plan.glob.constraints]
    for a in attempts[-2:]:
        n = a.get("n", "?")
        v = a.get("verdict") or {}
        reasons = ", ".join(v.get("reasons") or []) or "judge red"
        lines += ["", f"PRIOR ATTEMPT {n}: FAILED ({reasons})."]
        if v.get("unapproved"):
            lines.append("  Files outside SCOPE were changed and that work was discarded: " + ", ".join(v["unapproved"]))
        if v.get("tampered"):
            lines.append("  Judge files were modified and that work was discarded: " + ", ".join(v["tampered"]))
        if v.get("judge_output"):
            lines += ["  Judge output tail:", _tail(v["judge_output"])]
    lines += [
        "",
        "Work in this worktree. Run the judge yourself before you stop. Commit on green with the message",
        f'"{item.id}: <what>". If you cannot reach the target, stop and report the miss with the real judge',
        "output: smallest real attempt, measured gap, blocker. That is a good result. Do not special-case the",
        "judge in production code. Do not edit anything outside SCOPE. Finish by filling the JSON schema you were given.",
    ]
    return "\n".join(lines)
