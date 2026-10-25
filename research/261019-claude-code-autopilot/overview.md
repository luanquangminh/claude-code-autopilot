# Claude Code Autopilot: Research Overview

Team research, 2026-10-19/20. Roster: steer-lead (opus brain), g-loop-en, g-plan-en, g-zh (sonnet gatherers), verifier (sonnet), supervisor = main session. Languages EN + ZH + ZH-TW. Load-bearing claims were checked against source code or official docs; verdicts in [verifier-log.md](verifier-log.md).

## Question

Build a Claude Code pipeline that generates a plan, reviews it, synthesizes a per-task prompt, runs a headless implementation session, judges the result outside the model, and loops fresh sessions until every item passes, honestly. Backbone: [samhvw8/ambition-skill](https://github.com/samhvw8/ambition-skill) (locked contract, outside judge, honest miss, `receipts.py`, judged headless runner).

## Answer

**Nobody ships this end to end.** Of 9 plan tools, 8 loop tools and 2 official primitives read at source level, none binds each plan item to a locked executable check run by someone other than the implementer. "Done" is always a string the model emits, a flag it flips, or another LLM's reading of its transcript. The loop half is commodity. The honest half is the gap.

**Build** an orchestrator in code (Python over `claude -p --output-format stream-json`; move to the Agent SDK if you need in-process hooks) that:

1. turns the plan into a contract: one executable judge per item, authored and approved before work, committed to a git ref the implementer never writes;
2. runs one fresh `claude -p` session per item with hard caps (turns, budget, wall clock, tool allowlist);
3. judges the end state itself: judge command from the ref, tamper diff on judge paths, receipts against the transcript, zero commits = fail; never the exit code or the model's text;
4. loops on a miss with the judge output fed back, up to the item's stop line, then records an honest miss and moves on;
5. ends on a branch with a plan-vs-actual report; never auto-merges.

ambition-skill already supplies the contract format, `receipts.py`, the honest-miss rule, the report format and a judged headless runner. What is missing is the per-item state machine, the plan lint, the end-state tamper checks and the stop logic. See [architecture.md](architecture.md).

**Reference implementations to read, not adopt:** [red-green-mode](https://github.com/hidevinliu/red-green-mode) (per-item contract, non-LLM gate, fail-closed Stop hook, SHA-256 lock; 11 stars, self-benchmarked, disarmable) and [continuous-claude](https://github.com/AnandChowdhary/continuous-claude) (shell script merges on green CI, discards on red; agent can still edit tests in its own PR).

## Hypothesis verdicts

| id | Claim | Verdict |
|---|---|---|
| H1 | Loop half solved; termination honesty not | **supported, high.** Official `ralph-wiggum` loops in one session, done = literal `<promise>` match, every error path fails open |
| H2 | Anthropic harness `feature_list.json` is the canonical plan artifact | **supported, high**, but the coding agent flips `passes` itself |
| H3 | No tool binds a plan item to a locked executable judge plus stop line | **supported, high.** 0 of 9 plan tools; ralphex refuted at source; continuous-claude gates at merge, not per item; red-green-mode closest but disarmable |
| H4 | Headless control knobs | covered; `--bare` needs an API key |
| H5 | Failure modes: runaway, context loss, tampering, false done | supported; measured incidents in [evidence.md](evidence.md) |
| H6 | Orchestrator state machine in code; review the diff, not the plan | **supported, official** (best-practices doc) |
| H7 | LLM orchestrators fabricate subagent results | plausible, unmeasured (one unreproduced issue) |
| H8 | Judge integrity must be enforced in code on the end state | **supported, high.** Deny rules have open bypasses (#92542, #103241) |
| H9 | Unattended success tracks task verifiability | supported, EN and ZH agree |
| H10 | Terminal state = branch awaiting a human | supported (practice, not measured) |
| H11 | Hide the scorer from the implementer | hypothesis only; METR's 43x compares task suites |
| H12 | Process success is not task success (`claude -p` exit 0 on do-nothing runs) | **supported, verified.** iThome lab (4 of 4, 13 of 13) and the verifier's local repro on 2.1.286: exit 0, `subtype: success`, file never created |

## Files

| File | What |
|---|---|
| [architecture.md](architecture.md) | The recommended pipeline, stage by stage, with the evidence behind each choice |
| [contract-and-prompt.md](contract-and-prompt.md) | Plan contract schema, per-item prompt, structured self-report, `claude -p` invocation |
| [loop-primitives.md](loop-primitives.md) | Every loop primitive found, verified mechanics, use or avoid |
| [judge-integrity.md](judge-integrity.md) | Keeping the judge outside the model: layers, holes, Stop-hook rules |
| [evidence.md](evidence.md) | Numbers, resolved contradictions, unresolved questions, coverage limits |
| Raw reports | [en-loop-mechanics.md](en-loop-mechanics.md), [en-plan-review-prompt.md](en-plan-review-prompt.md), [en-failure-modes.md](en-failure-modes.md), [zh-community.md](zh-community.md), [zh-tw-community.md](zh-tw-community.md), [steer-log.md](steer-log.md), [verifier-log.md](verifier-log.md), [brief.md](brief.md) |

## Coverage limits

Reddit and Lobste.rs unreachable; linux.do and Zhihu blocked; ZH-TW rests on one deep source; no A/B of same-session versus fresh-context loops exists anywhere; EN dollar figures for runaway loops are secondhand, the firsthand ones are Chinese.
