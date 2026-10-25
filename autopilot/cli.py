"""autopilot CLI: lint | lock | run | report | plan | review."""
from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import sys
import time
from pathlib import Path

from . import gitx
from .lint import lint
from .lock import LockInfo, load_locked, lock, verify_ref
from .loop import Run, RunConfig, RunLocked, run_lock
from .plan import Plan, load, save
from .report import render
from .runner import SessionConfig
from .sessions import plan_pipeline, review_plan


def log(msg: str) -> None:
    print(f"[autopilot] {msg}", file=sys.stderr, flush=True)


def default_run_dir(repo: Path, plan_id: str) -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", "~/.local/state")).expanduser()
    return base / "autopilot" / repo.resolve().name / plan_id


def add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--repo", default=".", help="target git repository (default: cwd)")
    p.add_argument("--run-dir", help="state directory, kept outside the repo (default: ~/.local/state/autopilot/<repo>/<plan_id>)")
    p.add_argument("--claude-cmd", default="claude", help="command that runs Claude Code (tests use a fake)")
    p.add_argument("--model", help="override the plan's model")
    p.add_argument("--max-turns", type=int, default=None, help="pass --max-turns to claude (default: plan.global.max_turns)")
    p.add_argument("--allow-api-key", action="store_true",
                   help="permit sessions to use ANTHROPIC_API_KEY or a key helper. Default: subscription only; key "
                        "variables are scrubbed and a session that reports a key halts the run")


def run_config(args: argparse.Namespace, run_dir: Path, plan: Plan | None = None) -> RunConfig:
    max_turns = args.max_turns if args.max_turns is not None else (plan.glob.max_turns if plan else None)
    return RunConfig(run_dir=run_dir, claude_cmd=shlex.split(args.claude_cmd), model=args.model,
                     max_turns=max_turns, log=log, auth=auth_of(args))


def auth_of(args: argparse.Namespace) -> str:
    return "api-key" if getattr(args, "allow_api_key", False) else "subscription"


def session_config(args: argparse.Namespace, model: str, budget: float, timeout_s: float) -> SessionConfig:
    return SessionConfig(claude_cmd=shlex.split(args.claude_cmd), model=args.model or model,
                         max_turns=args.max_turns or 60, max_budget_usd=budget, timeout_s=timeout_s,
                         auth=auth_of(args))


def cmd_lint(args: argparse.Namespace) -> int:
    plan = load(args.plan)
    repo = Path(args.repo)
    if not plan.base_sha:
        plan.base_sha = gitx.head(repo)
    problems = lint(plan, repo, run_judges=not args.no_judge, log=log)
    for p in problems:
        print(f"FAIL {p}")
    if not problems:
        print(f"ok   plan {plan.plan_id}: {len(plan.items)} item(s), every judge red on {gitx.short(plan.base_sha)}")
    return 2 if problems else 0


def archive_previous(run_dir: Path, repo: Path, plan_id: str) -> None:
    """A new contract gets a clean run dir and branch; the old ones are kept, renamed by time."""
    ts = time.strftime("%y%m%d-%H%M%S")
    arch = run_dir / "archive" / ts
    moved: list[str] = []
    for name in ("state.json", "report.md", "lock.json", "contract", "attempts"):
        src = run_dir / name
        if src.exists():
            arch.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(arch / name))
            moved.append(name)
    wt = run_dir / "worktree"
    if (wt / ".git").exists():
        gitx.worktree_remove(repo, wt)
        moved.append("worktree")
    branch = f"autopilot/{plan_id}"
    if gitx.branch_exists(repo, branch):
        gitx.git(repo, "branch", "-m", branch, f"{branch}-{ts}")
        moved.append(f"branch -> {branch}-{ts}")
    if moved:
        log(f"archived previous run ({', '.join(moved)}) under {arch}")


def ensure_lock(plan: Plan, repo: Path, run_dir: Path, relock: bool = False) -> tuple[Plan, LockInfo]:
    lock_path = run_dir / "lock.json"
    if lock_path.exists():
        info = LockInfo.load(lock_path)
        bad = verify_ref(info, repo)
        if not relock and bad is None and info.base_sha == gitx.rev_parse(repo, plan.base_sha):
            log(f"using locked contract {gitx.short(info.contract_commit)} from {run_dir}")
            return load_locked(info, repo), info
        log(f"existing lock not reused ({'relock requested' if relock else bad or 'base changed'}); locking again")
        archive_previous(run_dir, repo, plan.plan_id)
    elif (run_dir / "state.json").exists() or (run_dir / "worktree" / ".git").exists():
        archive_previous(run_dir, repo, plan.plan_id)
    info = lock(plan, repo, run_dir)
    log(f"locked {plan.contract_ref} = {gitx.short(info.contract_commit)} (base {gitx.short(info.base_sha)})")
    return load_locked(info, repo), info


def exit_code(state: dict) -> int:
    """0 all green; 1 done with misses, blocks or regressions; 3 halted or errored."""
    if state.get("status") != "done":
        return 3
    return 0 if all(i["status"] == "green" for i in state["items"]) else 1


def cmd_lock(args: argparse.Namespace) -> int:
    plan = load(args.plan)
    repo = Path(args.repo)
    if not plan.base_sha:
        plan.base_sha = gitx.head(repo)
    problems = lint(plan, repo, log=log)
    for p in problems:
        print(f"FAIL {p}")
    if problems:
        return 2
    run_dir = Path(args.run_dir) if args.run_dir else default_run_dir(repo, plan.plan_id)
    try:
        with run_lock(run_dir):
            _, info = ensure_lock(plan, repo, run_dir, relock=True)
    except RunLocked as e:
        print(f"FAIL {e}")
        return 4
    print(f"ok   {info.ref} -> {info.contract_commit}  run-dir {run_dir}")
    return 0


def do_run(plan: Plan, repo: Path, run_dir: Path, cfg: RunConfig, skip_lint: bool = False,
           relock: bool = False) -> int:
    if not plan.base_sha:
        plan.base_sha = gitx.head(repo)
    if not skip_lint:
        problems = lint(plan, repo, log=log)
        for p in problems:
            print(f"FAIL {p}")
        if problems:
            return 2
    try:
        with run_lock(run_dir):
            plan, info = ensure_lock(plan, repo, run_dir, relock)
            run = Run(plan, info, repo, cfg)
            try:
                state = run.run()
            except Exception as e:                # state was halted and saved by Run.run
                state = run.state
                print(f"FAIL {type(e).__name__}: {e}")
    except RunLocked as e:
        print(f"FAIL {e}")
        return 4
    md = render(plan, state)
    (run_dir / "report.md").write_text(md)
    print(md)
    print(f"report: {run_dir / 'report.md'}")
    return exit_code(state)


def cmd_run(args: argparse.Namespace) -> int:
    plan = load(args.plan)
    repo = Path(args.repo)
    run_dir = Path(args.run_dir) if args.run_dir else default_run_dir(repo, plan.plan_id)
    return do_run(plan, repo, run_dir, run_config(args, run_dir, plan), args.skip_lint, args.relock)


def cmd_report(args: argparse.Namespace) -> int:
    import json
    run_dir = Path(args.run_dir)
    plan = load(run_dir / "contract" / "plan.json")
    state = json.loads((run_dir / "state.json").read_text())
    print(render(plan, state))
    return 0


def slug(task: str) -> str:
    words = re.findall(r"[a-z0-9]+", task.lower())[:4]
    return "-".join(words) or "task"


def cmd_plan(args: argparse.Namespace) -> int:
    repo = Path(args.repo)
    if gitx.is_dirty(repo):
        print("FAIL repo has uncommitted changes; commit or stash first (judge files get committed on this branch)")
        return 2
    plan_id = args.plan_id or f"{time.strftime('%y%m%d-%H%M')}-{slug(args.task)}"
    run_dir = Path(args.run_dir) if args.run_dir else default_run_dir(repo, plan_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    scfg = session_config(args, args.model or "claude-sonnet-5-5", args.budget, args.timeout)
    plan, problems, reviews, cost = plan_pipeline(args.task, repo, plan_id, scfg, run_dir / "planning", log, args.rounds)
    print(f"planning cost: ${cost:.2f}")
    hard = [p for p in problems if p.code != "review_not_approved"]
    if plan is None or hard:
        for p in problems:
            print(f"FAIL {p}")
        return 2
    out = run_dir / "plan.json"
    save(plan, out)
    for i, rv in enumerate(reviews, 1):
        print(f"review {i}: {rv.get('verdict')}; cut={rv.get('cut') or []}; gaps={len(rv.get('gaps') or [])}; {rv.get('notes', '')[:200]}")
    print(f"plan written: {out}")
    for it in plan.items:
        print(f"  - {it.id}: {it.goal} | judge `{it.judge.cmd}` | scope {it.scope} | stop line {it.stop_line}")
    if problems:
        print(f"WARN {problems[0]}")
    if not args.auto_approve:
        print(f"approve with:  python3 -m autopilot run {shlex.quote(str(out))} --repo {shlex.quote(str(repo))} --run-dir {shlex.quote(str(run_dir))}")
        return 0
    if problems:
        print("FAIL auto-approve refused: the reviewer did not approve this plan; read it and run it yourself")
        return 2
    log("auto-approve: the literal plan is pre-approved; locking and running")
    return do_run(plan, repo, run_dir, run_config(args, run_dir, plan), skip_lint=True)


def cmd_review(args: argparse.Namespace) -> int:
    plan = load(args.plan)
    repo = Path(args.repo)
    run_dir = Path(args.run_dir) if args.run_dir else default_run_dir(repo, plan.plan_id)
    scfg = session_config(args, args.model or plan.glob.model, args.budget, args.timeout)
    review, sess = review_plan(plan, repo, scfg, run_dir / "planning", 1)
    import json
    print(json.dumps(review, indent=2) if review else f"no review ({sess.subtype})")
    print(f"cost: ${sess.total_cost_usd:.2f}")
    return 0 if review else 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="autopilot", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("lint", help="check a plan: schema, judge paths, overlap, judge red on baseline")
    p.add_argument("plan"); p.add_argument("--no-judge", action="store_true", help="skip running judges on the baseline")
    add_common(p); p.set_defaults(fn=cmd_lint)
    p = sub.add_parser("lock", help="lint then lock the contract into refs/contract/<plan_id>")
    p.add_argument("plan"); add_common(p); p.set_defaults(fn=cmd_lock)
    p = sub.add_parser("run", help="lint, lock (if needed), run every item, write the report")
    p.add_argument("plan"); p.add_argument("--skip-lint", action="store_true"); p.add_argument("--relock", action="store_true")
    add_common(p); p.set_defaults(fn=cmd_run)
    p = sub.add_parser("report", help="re-render the report from state.json")
    p.add_argument("--run-dir", required=True); p.set_defaults(fn=cmd_report)
    p = sub.add_parser("plan", help="draft a plan with the model, commit judge files, lint, review")
    p.add_argument("task"); p.add_argument("--plan-id"); p.add_argument("--rounds", type=int, default=2)
    p.add_argument("--auto-approve", action="store_true", help="unattended: lock and run right after planning")
    p.add_argument("--budget", type=float, default=3.0, help="USD cap per planning session")
    p.add_argument("--timeout", type=float, default=1200, help="seconds per planning session")
    add_common(p); p.set_defaults(fn=cmd_plan)
    p = sub.add_parser("review", help="one read-only review round of an existing plan")
    p.add_argument("plan"); p.add_argument("--budget", type=float, default=1.0); p.add_argument("--timeout", type=float, default=600)
    add_common(p); p.set_defaults(fn=cmd_review)
    args = ap.parse_args(argv)
    return args.fn(args)
