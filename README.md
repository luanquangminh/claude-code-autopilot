# autopilot

A code orchestrator that runs Claude Code headlessly against a **locked plan contract**:
draft a plan with one executable judge per item, lint it (every judge must be red on the
baseline), review it, lock it into a git ref the implementer never writes, run one fresh
`claude -p` session per attempt, judge the **committed end state** in code, loop to the
item's stop line, record honest misses, and leave a branch plus a plan-vs-actual report.
It never merges and never trusts the exit code or the model's text.

Design and evidence: `plans/20261020-0402-autopilot-orchestrator/` and
`research/261019-claude-code-autopilot/`. Contract rules follow
[samhvw8/ambition-skill](https://github.com/samhvw8/ambition-skill).

## Run

```bash
cd autopilot
python3 -m unittest discover -s tests -t .            # 40 tests, fake claude, ~40 s

# hand-written plan (see examples/plan-example.json); base_sha "" means HEAD
python3 -m autopilot lint examples/plan-example.json --repo /path/to/repo
python3 -m autopilot run  examples/plan-example.json --repo /path/to/repo --run-dir /path/outside/repo

# let the model draft the plan, commit judge files, lint, review; then approve by running
python3 -m autopilot plan "Fix the off-by-one in paginate()" --repo /path/to/repo
python3 -m autopilot plan "..." --repo /path/to/repo --auto-approve     # unattended
python3 -m autopilot report --run-dir <run-dir>
```

Python 3.11, standard library only. `claude` 2.1.x on PATH (or `--claude-cmd`).

## What the loop does

| Stage | Who | Decides with |
|---|---|---|
| plan draft | `claude -p`, write access to judge files only in practice | nothing; output is a claim |
| lint | code | schema; judge paths committed; `scope ∩ judge.paths = ∅`; judge exits non-zero on `base_sha` |
| review | fresh read-only `claude -p`, ≤ 2 rounds | cuts scope; only a `high` gap triggers a revision |
| lock | code | `plan.json` + judge files → `refs/contract/<plan_id>`, sha256 per file, copy outside the repo |
| implement | fresh `claude -p` per attempt in `run_dir/worktree` on branch `autopilot/<plan_id>` | hard caps: `--max-budget-usd`, `--max-turns`, wall clock, tool allowlist, `--permission-prompts none` |
| judge | code, on committed HEAD | ref intact → ≥ 1 commit → judge files untouched → scope → receipts → judge cmd in a clean checkout with judge files overlaid from the ref |
| loop | code | stop line, no-progress limit, cost / wall / attempt caps, `STOP` file, `run.lock` |
| report | code | ambition plan-vs-actual table, deviations, unapproved files, next rung |

Attempt outcomes: `PASS` (with `canary ok` when a canary could be derived); `FAIL zero_commits`;
`FAIL judge_tampered`, `out_of_scope`, `branch_detached`, `history_rewritten` (branch restored to
the attempt's start; `scope_policy: report` lists instead of failing); `FAIL judge_red` /
`judge_timed_out`; `FAIL judge_oracle_broken` (the judge also exited 0 with a failing canary test
present, so its exit code no longer means anything); `fake_receipt` (deviation, or a failure with
`strict_receipts`). A self-report with `blocker_kind: judge_contradicts_spec` marks the item
**blocked** for a human. After the last item every green item is re-judged on the final HEAD;
failures become **regressed**. A moved contract ref, or a CLI that produces no output, halts the run.
A session that dies without a `result` event is charged the full per-attempt budget against the cap.

Canary: for `unittest discover` (honouring `-s`/`-p`) and pytest on a directory, the orchestrator
derives a test file that must fail; set `judge.canary {path, content}` for other runners, else the
report says `canary none` and only the exit code protects you.

Exit codes: 0 all items green · 1 done with misses, blocks or regressions · 2 lint or approval
refused · 3 halted or errored · 4 another run holds the lock.

## State files (`--run-dir`, default `~/.local/state/autopilot/<repo>/<plan_id>`)

`plan.json` (drafted) · `lock.json` · `contract/` (locked plan + judge files) · `worktree/` ·
`attempts/<item>-<n>/implement.{prompt.txt,argv.json,transcript.jsonl,stderr.txt}` ·
`planning/` · `state.json` · `report.md` · `STOP` (create to halt after the current attempt) ·
`run.lock`.

## Limits

- The judge files are protected by end-state checks and the ref, not by a sandbox. A session
  with `Write` can still reach paths outside the worktree; an OS sandbox is the real answer.
- Special-casing production code to satisfy a test is not caught by any layer here; the plan
  review and a human on the branch are the mitigation. The canary only proves the judge still
  fails when a test fails; added lines mentioning `os._exit`, `atexit`, `unittest`, `pytest`,
  `sys.modules` or `SystemExit` are listed under Deviations, not blocked.
- Items run sequentially on one branch; no parallelism, no auto-merge, by design.
- `--bare` is not used (OAuth logins need `--setting-sources`); project hooks in the target
  repo still run under `-p`.
