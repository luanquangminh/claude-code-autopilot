# Phase 4 — Plan Draft and Review Sessions

Status: done (tests/test_sessions.py) · Priority: high · Depends on: phases 1–2

## Files
| Action | Path | Content |
|---|---|---|
| create | `autopilot/sessions.py` | `draft_plan(task, repo, cfg)`, `review_plan(plan, repo, cfg)`; both via `runner.run_session` with their own schemas and tool lists |
| modify | `autopilot/cli.py` | `plan <task>` = draft → commit judge files → lint (≤2 rounds with feedback) → review (≤2 rounds) → print; `--auto-approve` chains lock + run |

## Draft session
- Tools: Read, Glob, Grep, Write, Edit, `Bash(python3:*)`, `Bash(git status:*)`, `Bash(git diff:*)`, `Bash(git log:*)`.
- Prompt: the task + plan schema + rules: one executable judge per item, judge must FAIL today, judge files under `tests/` or a stated path, scope = literal request, `target.state`, `stop_line`, optional `next_rung`.
- Output: `structured_output` = plan JSON (without `base_sha`, `contract_ref`, sha256).
- Orchestrator: `git add` judge paths, commit `contract: judge files for <plan_id>` → `base_sha`; lint; on problems, one revision session with the problems pasted.

## Review session
- Tools: Read, Glob, Grep only. Fresh session, sees plan + repo.
- Schema: `{verdict: approve|revise, cut: [item ids], gaps: [{item, severity, note}], notes}`.
- Rules (from the research): criteria = the contract; cut scope; flag requirement gaps only; no finding quota; high severity only triggers a revision; max 2 rounds; then a human (or `--auto-approve`).

## Success criteria
- `tests/test_sessions.py`: fake planner returns a plan whose judge is green on baseline → lint problems fed back → second fake output passes; fake reviewer `revise` once → one revision → proceeds.
