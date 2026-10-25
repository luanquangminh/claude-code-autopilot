# Phase 3 — Loop, Caps, Report

Status: done (tests/test_loop.py) · Priority: critical · Depends on: phase 2

## Files
| Action | Path | Content |
|---|---|---|
| create | `autopilot/loop.py` | `run_plan(plan_path, repo, run_dir, cfg)`: state machine; `state.json` persisted after every attempt |
| create | `autopilot/report.py` | `render(state) -> str` plan-vs-actual markdown; written to `run_dir/report.md` |
| create | `autopilot/cli.py`, `autopilot/__main__.py` | `autopilot lint|lock|run|report|plan|review` |

## State machine
```
for item in plan.items (sequential, same branch autopilot/<plan_id>):
  while attempts < stop_line and not halted:
    start_sha = HEAD
    brief = build_brief(item, prior judge outputs)
    session = run_session(brief)            # fresh claude -p
    verdict = judge_attempt(...)
    record attempt {start_sha, end_sha, verdict, cost, turns, subtype, claims}
    if verdict.pass: item.status = green; break
    if verdict.reason in (judge_tampered, out_of_scope, contract_ref_tampered): git reset --hard start_sha
    if claim.blocker_kind == judge_contradicts_spec: item.status = blocked; break   # human decides
    if no progress (tree(end)==tree(start)) for no_progress_limit attempts: break
    check caps: total cost, wall clock, max_attempts_total, STOP file → halted
  if not green and not blocked: item.status = missed; item.miss = last claim or synthesized
```
- Lock file `run_dir/run.lock` with pid; refuse a second concurrent run.
- Branch `autopilot/<plan_id>` created at `base_sha` in a worktree under `run_dir/worktree`. Left in place at the end.
- Misses never block the run; halts do.

## Report (ambition plan-vs-actual)
Per item: Judge planned vs actual (exit + tail), Target planned vs reached/missed, Scope rows done/not done, attempts, cost. Then `Deviations` (tamper, reset events), `Unapproved` (out-of-scope files seen), `Next rung` (plan field or none). Run summary: counts, total cost, wall time, branch name, "not merged".

## Success criteria (build-order checks)
- a-honest with a fake that fixes the real bug and claims `judge_contradicts_spec` → item `blocked`, tests untouched, 1 attempt; with a fake that keeps trying → `missed` at stop line 3.
- a2-speed with 3 non-progress fakes → `missed` at stop line; next item still runs.
- b-scope with README edit then clean fix → attempt 1 `out_of_scope` + reset, attempt 2 `green`; report lists README.md under Unapproved.
- Caps: `max_cost_usd` exceeded → `halted`; STOP file → `halted` after current attempt; `max_attempts_total`.
