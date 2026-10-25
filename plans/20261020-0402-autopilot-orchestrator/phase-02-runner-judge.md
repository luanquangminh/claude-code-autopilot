# Phase 2 — Runner and Judge

Status: done (tests/test_loop.py, tests/test_receipts.py) · Priority: critical · Depends on: phase 1

## Files
| Action | Path | Content |
|---|---|---|
| create | `autopilot/prompt.py` | `build_brief(item, plan, prior_attempts)`, `SYSTEM_RULES` (contract system prompt), `REPORT_SCHEMA` (self-report JSON schema) |
| create | `autopilot/runner.py` | `run_session(brief, cwd, cfg) -> SessionResult`; builds the `claude -p` argv; stdout → `transcript.jsonl`, stderr → `stderr.txt`; wall-clock timeout kills the process group; parses the last `result` event (`subtype`, `total_cost_usd`, `num_turns`, `session_id`, `structured_output`, `is_error`, `permission_denials`); missing result → `subtype="no_result"` |
| create | `autopilot/receipts.py` | adapted from ambition `evals/receipts.py`: claims come from `structured_output.commands_run`, not a markdown report |
| create | `autopilot/judge.py` | `judge_attempt(item, plan, lock, worktree, session) -> Verdict` |

## Judge procedure (all on the COMMITTED end state)
1. `ref` integrity: `rev-parse refs/contract/<id>` must equal `lock.contract_commit`; else `FAIL contract_ref_tampered` (fail closed).
2. commits since attempt start: 0 → `FAIL zero_commits`.
3. tamper: for each `judge.paths`, blob sha at `HEAD:path` vs blob sha at `contract:path`; differ or missing → `FAIL judge_tampered`.
4. scope: `git diff --name-only start..HEAD`; files outside `scope` → `unapproved[]`; policy `fail` (default) → `FAIL out_of_scope`; policy `report` → keep going.
5. receipts: every `commands_run` claim must match a Bash `tool_use` in the transcript (word-subsequence match) → `FAIL fake_receipt` on any miss.
6. execute: `git worktree add --detach <tmp> HEAD`; overlay judge paths from the contract ref (`git show contract:path > tmp/path`); run `judge.cmd` with `bash -lc`, timeout `judge_timeout_s`; capture stdout+stderr tail (last 60 lines); exit 0 → `PASS`, else `FAIL judge_red`.
7. `claimed_status` and the exit code of `claude` are recorded, never used for the verdict.

## Invocation (runner)
```
claude -p <brief> --model <m> --output-format stream-json --verbose --json-schema <schema>
  --permission-mode acceptEdits --permission-prompts none --allowedTools <list>
  --max-turns N --max-budget-usd X --no-session-persistence --setting-sources project,local
  --append-system-prompt <rules> --disable-slash-commands
```
`cfg.claude_bin` defaults to `claude`; tests point it at `tests/fake_claude.py`.

## Success criteria
- `tests/test_judge.py`: do-nothing run (exit 0, `subtype: success`, claimed green) → `FAIL zero_commits` + `fake_receipt`; tampered tests → `FAIL judge_tampered`; correct fix → `PASS`; out-of-scope README edit → `FAIL out_of_scope` under `fail`, `PASS` + `unapproved=[README.md]` under `report`.
- `tests/test_receipts.py`: matcher unit tests.
