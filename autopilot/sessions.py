"""Model-run stages: plan draft and plan review. Their outputs are claims; lint and the human gate decide."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from . import gitx
from .lint import Problem, lint
from .plan import Plan, from_dict, to_dict
from .runner import SessionConfig, SessionResult, run_session

PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["plan_id", "items", "next_rung", "constraints"],
    "properties": {
        "plan_id": {"type": "string"},
        "task": {"type": "string"},
        "items": {"type": "array", "items": {
            "type": "object",
            "required": ["id", "goal", "scope", "judge", "target", "stop_line"],
            "properties": {
                "id": {"type": "string", "description": "kebab-case, unique"},
                "goal": {"type": "string"},
                "scope": {"type": "array", "items": {"type": "string"}, "description": "files the implementer may change"},
                "judge": {"type": "object", "required": ["cmd", "paths"], "properties": {
                    "cmd": {"type": "string", "description": "one shell command; exit 0 only when done; must fail today"},
                    "paths": {"type": "array", "items": {"type": "string"}, "description": "files the judge depends on; locked"}}},
                "target": {"type": "object", "required": ["value", "state"], "properties": {
                    "value": {"type": "string"},
                    "state": {"type": "string", "description": "proven (<source>) | unreasonable on purpose | guess (no baseline)"}}},
                "stop_line": {"type": "integer"},
                "interfaces": {"type": "string"},
                "notes": {"type": "string"}}}},
        "next_rung": {"type": "string", "description": "the bigger step, proposed, not done"},
        "constraints": {"type": "string", "description": "global constraints every item must respect"},
    },
}

REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["verdict", "cut", "gaps", "notes"],
    "properties": {
        "verdict": {"type": "string", "enum": ["approve", "revise"]},
        "cut": {"type": "array", "items": {"type": "string"}, "description": "item ids to drop as scope creep"},
        "gaps": {"type": "array", "items": {"type": "object", "required": ["item", "severity", "note"], "properties": {
            "item": {"type": "string"}, "severity": {"type": "string", "enum": ["high", "medium", "low"]},
            "note": {"type": "string"}}}},
        "notes": {"type": "string"},
    },
}

DRAFT_TOOLS = ["Read", "Glob", "Grep", "Write", "Edit", "Bash(python3:*)", "Bash(ls:*)",
               "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)"]
REVIEW_TOOLS = ["Read", "Glob", "Grep"]

DRAFT_SYSTEM = """You are the planning session of an automated pipeline. You write a plan contract. Code will lint it (every judge must fail on today's code), a separate reviewer will cut scope, a human approves, then fresh sessions implement one item each and code judges the committed result. You do not implement anything. Judge files you write (tests, fixtures) are committed by the orchestrator; do not commit."""

REVIEW_SYSTEM = """You are a read-only plan reviewer inside an automated pipeline. The plan is the contract. Your job is to cut scope creep and to flag requirement gaps, nothing else. Do not invent findings to look thorough; if the plan is sound, approve it with no gaps. Only a high-severity gap triggers a revision. You cannot edit files."""


def draft_prompt(task: str, plan_id: str, feedback: list[str] | None = None) -> str:
    lines = [f"Write the plan contract for this task. plan_id must be {plan_id!r}.", "", "TASK:", task, "",
             "Rules for every item:",
             "- judge.cmd: one shell command, runnable from the repo root in a clean checkout, that exits non-zero TODAY and exits 0 only when the item is truly done. If no such check exists, write a test under tests/ now and name it in judge.paths.",
             "- judge.paths: every file the judge depends on that the implementer must not touch (tests, fixtures, data).",
             "- scope: the files the implementer may change. Must not overlap judge.paths. Literal request only.",
             "- target.value: a number or count. target.state: 'proven (<source>)', 'unreasonable on purpose', or 'guess (no baseline)'.",
             "- stop_line: attempts allowed before an honest miss, 1 to 5.",
             "- Order items so each builds on the previous; one branch carries them all.",
             "Anything bigger than the literal request goes into next_rung, not into items.",
             "Finish by filling the JSON schema you were given."]
    if feedback:
        lines += ["", "THE PREVIOUS DRAFT WAS REJECTED. Fix these and output the full plan again:"] + [f"- {f}" for f in feedback]
    return "\n".join(lines)


def review_prompt(plan: Plan) -> str:
    import json
    return "\n".join([
        "Review this plan contract against the task. Criteria: (1) each item's judge actually proves its goal;",
        "(2) scope is the literal request, no more; (3) a requirement of the task has no item (gap).",
        "Cut items that are scope creep (list their ids in `cut`). Report gaps with a severity; only `high` means",
        "the plan cannot ship as is. Max two rounds happen; be decisive. Approve when sound.", "",
        "TASK:", plan.task or "(see plan)", "", "PLAN:", json.dumps(to_dict(plan), indent=2)])


def plan_from_output(so: dict[str, Any], plan_id: str, task: str) -> Plan:
    d = dict(so)
    d["plan_id"] = plan_id
    d.setdefault("task", task)
    d["base_sha"] = ""
    g: dict[str, Any] = {}
    if d.get("constraints"):
        g["constraints"] = str(d.pop("constraints"))
    d["global"] = g
    return from_dict(d)


def draft_plan(task: str, repo: str | Path, plan_id: str, cfg: SessionConfig, out_dir: str | Path,
               feedback: list[str] | None = None, round_: int = 1) -> tuple[Plan | None, SessionResult]:
    c = replace(cfg, allowed_tools=list(DRAFT_TOOLS))
    sess = run_session(c, draft_prompt(task, plan_id, feedback), cwd=repo, out_dir=out_dir,
                       schema=PLAN_SCHEMA, system_prompt=DRAFT_SYSTEM, name=f"draft-{round_}")
    if not sess.structured_output:
        return None, sess
    try:
        return plan_from_output(sess.structured_output, plan_id, task), sess
    except (TypeError, ValueError, KeyError):
        return None, sess


def commit_judge_files(plan: Plan, repo: str | Path) -> str:
    """Commit every judge path on the current branch; returns the new base sha."""
    paths = sorted({p for it in plan.items for p in it.judge.paths})
    missing = [p for p in paths if not (Path(repo) / p).exists()]
    if missing:
        raise FileNotFoundError("judge paths not on disk: " + ", ".join(missing))
    if gitx.out(repo, "status", "--porcelain", "--", *paths):
        gitx.commit_paths(repo, paths, f"contract: judge files for {plan.plan_id}")
    return gitx.head(repo)


def review_plan(plan: Plan, repo: str | Path, cfg: SessionConfig, out_dir: str | Path,
                round_: int = 1) -> tuple[dict[str, Any] | None, SessionResult]:
    c = replace(cfg, allowed_tools=list(REVIEW_TOOLS))
    sess = run_session(c, review_prompt(plan), cwd=repo, out_dir=out_dir, schema=REVIEW_SCHEMA,
                       system_prompt=REVIEW_SYSTEM, name=f"review-{round_}")
    return sess.structured_output, sess


def apply_cuts(plan: Plan, review: dict[str, Any]) -> list[str]:
    cut = [c for c in (review.get("cut") or []) if any(it.id == c for it in plan.items)]
    if cut and len(cut) < len(plan.items):
        plan.items = [it for it in plan.items if it.id not in cut]
        return cut
    return []


def key_problem(sess: SessionResult, cfg: SessionConfig, stage: str) -> Problem | None:
    if cfg.auth == "subscription" and sess.used_api_key:
        return Problem("api_key_used", f"{stage} session used an API key ({sess.api_key_source}); "
                       "this run is subscription-only (pass --allow-api-key to permit it)")
    return None


def plan_pipeline(task: str, repo: str | Path, plan_id: str, cfg: SessionConfig, out_dir: str | Path,
                  log: Callable[[str], None] = print, rounds: int = 2
                  ) -> tuple[Plan | None, list[Problem], list[dict[str, Any]], float]:
    """draft -> commit judge files -> lint (<= rounds) -> review (<= rounds). Returns (plan, problems, reviews, cost)."""
    cost = 0.0
    feedback: list[str] | None = None
    plan: Plan | None = None
    problems: list[Problem] = []
    for r in range(1, rounds + 1):
        log(f"plan: draft round {r}")
        plan, sess = draft_plan(task, repo, plan_id, cfg, out_dir, feedback, r)
        cost += sess.total_cost_usd
        if bad := key_problem(sess, cfg, f"draft {r}"):
            return None, [bad], [], cost
        if plan is None:
            log(f"plan: draft {r} produced no plan ({sess.subtype})")
            problems = [Problem("no_plan", f"draft {r} returned no structured plan ({sess.subtype})")]
            continue
        plan.base_sha = commit_judge_files(plan, repo)
        problems = lint(plan, repo, log=log)
        if not problems:
            break
        log(f"plan: lint rejected draft {r}: " + "; ".join(str(p) for p in problems))
        feedback = [str(p) for p in problems]
    if plan is None or problems:
        return plan, problems, [], cost
    reviews: list[dict[str, Any]] = []
    for r in range(1, rounds + 1):
        log(f"plan: review round {r}")
        review, sess = review_plan(plan, repo, cfg, out_dir, r)
        cost += sess.total_cost_usd
        if bad := key_problem(sess, cfg, f"review {r}"):
            return plan, [bad], reviews, cost
        if review is None:
            log(f"plan: review {r} returned nothing ({sess.subtype}); continuing without it")
            break
        reviews.append(review)
        cut = apply_cuts(plan, review)
        if cut:
            log("plan: reviewer cut " + ", ".join(cut))
        high = [g for g in (review.get("gaps") or []) if g.get("severity") == "high"]
        if review.get("verdict") == "approve" and not high:
            break
        if r == rounds:
            log("plan: review rounds exhausted; the human gate decides")
            break
        feedback = [f"reviewer gap ({g.get('item', '?')}): {g.get('note', '')}" for g in high] or [f"reviewer: {review.get('notes', '')}"]
        log(f"plan: revision after review {r}")
        plan2, sess = draft_plan(task, repo, plan_id, cfg, out_dir, feedback, rounds + r)
        cost += sess.total_cost_usd
        if bad := key_problem(sess, cfg, f"revision {r}"):
            return plan, [bad], reviews, cost
        if plan2 is None:
            break
        plan2.base_sha = commit_judge_files(plan2, repo)
        p2 = lint(plan2, repo, log=log)
        if p2:
            log("plan: revision failed lint; keeping the previous plan: " + "; ".join(str(p) for p in p2))
            break
        plan = plan2
    last = reviews[-1] if reviews else None
    approved = bool(last) and last.get("verdict") == "approve" and not [
        g for g in (last.get("gaps") or []) if g.get("severity") == "high"]
    if not approved:
        problems = [Problem("review_not_approved", "no approving review without high-severity gaps; a human must approve")]
    return plan, problems, reviews, cost
