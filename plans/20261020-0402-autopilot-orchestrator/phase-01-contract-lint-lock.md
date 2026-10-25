# Phase 1 — Contract, Lint, Lock

Status: done (tests/test_plan_lint_lock.py) · Priority: critical · Depends on: nothing

## Context
- Contract shape: `research/.../contract-and-prompt.md`
- Rules: judge RED on baseline; `scope ∩ judge.paths = ∅`; `stop_line >= 1`; target state is `proven…`, `unreasonable on purpose`, or `guess…`

## Files
| Action | Path | Content |
|---|---|---|
| create | `autopilot/plan.py` | `Plan`, `Item`, `Judge`, `Target`, `Global` dataclasses; `load(path)`, `dump(plan)`, `validate(plan)` (schema-level) |
| create | `autopilot/gitx.py` | thin git helpers: `run_git`, `rev_parse`, `cat_file_exists`, `blob_sha`, `show`, `worktree_add/remove`, `commit_count`, `changed_files`, `tree_of` |
| create | `autopilot/lint.py` | `lint(plan, repo) -> list[Problem]`; runs each judge in a temp detached worktree at `base_sha`, expects non-zero exit |
| create | `autopilot/lock.py` | `lock(plan, repo) -> LockInfo`: temp index → `plan.json` + judge files → `write-tree` → `commit-tree` → `update-ref refs/contract/<plan_id>`; records sha256 per judge path; exports a copy to `run_dir/contract/` |
| create | `examples/plan-example.json` | the research example, adapted |

## Steps
1. `plan.py`: dataclasses + JSON load/dump; `validate` returns problems (ids unique, stop_line, target.state, judge.cmd non-empty, judge.paths non-empty).
2. `gitx.py`: every call is `subprocess.run([...], cwd=repo, capture_output=True, text=True, check=False)`; no shell strings (path has a space).
3. `lint.py`: schema problems first; then for each item: paths exist at `base_sha` (`git cat-file -e base:path`); scope/judge overlap (exact or directory prefix); judge red: `git worktree add --detach <tmp> base_sha`, run `judge.cmd` via `bash -lc` with timeout, exit 0 → problem "judge green on baseline (vacuous)"; `worktree remove --force`.
4. `lock.py`: refuse if lint has problems; build the ref; return `{contract_commit, ref, sha256: {path: hex}}`; write `plan.locked.json` with sha256s filled in.

## Success criteria
- `tests/test_lint.py`: green-on-baseline judge rejected; overlapping scope rejected; missing judge path rejected; valid plan passes.
- `tests/test_lock.py`: `git rev-parse refs/contract/<id>` resolves; `git show ref:plan.json` equals the locked plan; sha256 matches `git show base:tests/…`.

## Risks
- Judge commands that need deps: lint runs them in a worktree of the same repo, so any venv/mise config inside the repo is present. Document that the judge must be runnable from a clean checkout.
