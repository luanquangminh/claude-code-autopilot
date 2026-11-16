---
name: autopilot
description: Run a task unattended through the Claude Code autopilot. It drafts and reviews a plan, locks the judge contract in git, implements each item in fresh sessions inside a worktree, judges the committed result, and leaves a branch for review. Only runs when the user types /autopilot, because it spends subscription usage and creates branches.
argument-hint: "<task> [--repo <path>]"
disable-model-invocation: true
allowed-tools: Bash(autopilot *) Bash(git status *) Bash(git log *) Bash(gh pr create *)
---

# autopilot

Drive the `autopilot` CLI for the task in `$ARGUMENTS`. The CLI owns the whole loop: it plans
with the model, lints the plan so every judge fails on the base commit, locks it in
`refs/contract/<plan_id>`, runs one fresh `claude -p` session per attempt in a worktree on branch
`autopilot/<plan_id>`, judges the committed end state, and never merges. Your job is to launch
it, wait, and relay what it found. Do not re-judge or touch its branch: the report and the
branch are the deliverable, and a hand edit would break the receipts it kept.

## Before launching

| check | how | if it fails |
|---|---|---|
| CLI on PATH | `autopilot --help` | `mise use -g pipx:git+https://github.com/luanquangminh/claude-code-autopilot` |
| repo | `--repo` from the arguments, else the current directory | the CLI prints one `FAIL ...` line and exits 2 |
| clean tree | `git status --short` prints nothing | stop and say so: `plan` refuses a dirty repo because it commits judge files |

## Launch

A run takes 5 to 30 minutes, so start it in the background and wait for it to finish instead of
polling. Send stdout and stderr to a log file outside the repo.

```
autopilot plan "<task>" --repo <repo> --auto-approve \
  --claude-cmd "claude --settings '${CLAUDE_SKILL_DIR}/settings.json'"
```

The settings file turns off co-author trailers in the sessions, so the commits carry no
attribution. Pass `--plan-id` only when the user named one. Leave `--allow-api-key` off unless
the user asked for it: by default a session that reports an API key is refused, so the run only
draws on the subscription login.

## After it exits

The report is printed at the end of the log and saved at the `report:` path it names. Read the
exit code first:

| exit | meaning | show |
|---|---|---|
| 0 | every item green | the report table and the branch `autopilot/<plan_id>` |
| 1 | done, but an item missed its stop line, blocked, or regressed | that item's judge output and its attempts |
| 2 | plan refused: lint, reviewer, dirty repo, API key, or bad arguments | the `FAIL` lines |
| 3 | halted before done: no output from claude, or an exception | the halt reason from the report |
| 4 | another run holds this run directory's lock | the `FAIL` line; do not remove the lock |

Then report in this order: status per item, attempts and cost per session, deviations
(suspicious additions, fake receipts, out-of-scope files), the branch, the contract ref, and
the `report.md` path. Offer `gh pr create --draft --head autopilot/<plan_id>`. Never merge,
never delete the branch, and never rerun on your own: a rerun archives the previous state, and
whether to spend another run is the user's call.

## Related

- [README](https://github.com/luanquangminh/claude-code-autopilot#readme) explains the loop, state files and limits
