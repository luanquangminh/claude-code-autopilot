# Autopilot Orchestrator — Plan

Date: 2026-10-20 · Status: implemented and verified (suite + live smoke) · Source research: `../../research/261019-claude-code-autopilot/`

## Goal

A code orchestrator that takes a task, drafts a plan with one executable judge per item,
reviews and locks it, runs one fresh `claude -p` session per item, judges the end state
itself, loops to the stop line, records honest misses, and leaves a branch plus a
plan-vs-actual report. Never merges. Never trusts exit codes or model text.

## Decisions (from the research, not re-litigated here)

| Decision | Why | Source |
|---|---|---|
| Orchestrator in Python, stdlib only | SDK result fields are the state-machine inputs; no LLM in the control loop | architecture.md |
| Fresh `claude -p` per attempt, one worktree per run | context loss at 131K; one feature per session | evidence.md |
| Judge = command from `refs/contract/<id>`, run on the COMMITTED end state in a clean checkout | closes "verifier written by the judged party"; path denies are bypassable | judge-integrity.md |
| Zero commits = fail; receipts vs transcript; tamper diff on judge paths | exit 0 on do-nothing runs, claimed-but-not-run commands | evidence.md H12 |
| Lint: judge must be RED on `base_sha` | a judge green on baseline is vacuous | architecture.md |
| Hard caps in code: turns, $, wall clock, attempts, STOP file, lock file | 1,466-iteration $268 loop; 8-block cap resets | evidence.md |
| Honest miss after stop line; contradiction claim stops the item for a human | ambition rules | SKILL.md |
| Reviewers get the contract, cut scope, 1–2 rounds | reviewers over-find without criteria | judge-integrity.md |

## Phases

| # | Phase | File | Verify |
|---|---|---|---|
| 1 | Contract, lint, lock | [phase-01-contract-lint-lock.md](phase-01-contract-lint-lock.md) | lint rejects a judge green on baseline; ref holds plan + judge files with sha256 |
| 2 | Runner and judge | [phase-02-runner-judge.md](phase-02-runner-judge.md) | fake `claude` do-nothing run → FAIL (zero commits, fake receipts) despite exit 0 |
| 3 | Loop, caps, report | [phase-03-loop-caps-report.md](phase-03-loop-caps-report.md) | a-honest → honest miss, tests untouched; a2-speed stops at stop line, run continues; b-scope README change → Unapproved |
| 4 | Plan draft and review sessions | [phase-04-plan-review-sessions.md](phase-04-plan-review-sessions.md) | fake planner output passes lint; reviewer "revise" triggers one revision round then proceeds |
| 5 | Verification and live smoke | [phase-05-verification.md](phase-05-verification.md) | unittest suite green; one live `claude -p` run on b-scope under a $1 cap ends green on a branch |

## Layout

```
autopilot/
  autopilot/            package (cli, plan, lint, lock, gitx, prompt, runner, judge, receipts, loop, report, sessions)
  tests/                unittest; tests/fake_claude.py emulates `claude -p`
  examples/             plan-example.json
  plans/                this plan
```

## Out of scope (v1)

Blind-judging pipeline variants with `evals/judge/` (next step, not needed to ship); OS sandbox;
Agent SDK port; prose report by model; parallel items.

## Unresolved

- Whether `--permission-prompts none` is honoured for every tool under `acceptEdits` on 2.1.286 (checked in phase 5 live smoke).
- Workspace path contains a space; Python subprocess lists handle it, plugin hooks (#78490) are out of scope.
