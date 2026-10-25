# Steer Log — Claude Code Autopilot Pipeline

Owner: steer-lead. Phase: **CLOSED** — STOP approved by team-lead; synthesis complete (overview.md, architecture.md, contract-and-prompt.md, loop-primitives.md, judge-integrity.md, evidence.md). All agents released.
Supervisor = `team-lead`. Reports: en-loop-mechanics.md, en-plan-review-prompt.md (+judge integrity), en-failure-modes.md, zh-community.md, [zh-tw-community.md], verifier-log.md.

## Hypotheses (final status unless noted)

| id | statement | status | conf | key sources |
|---|---|---|---|---|
| H1 | Loop half solved; termination honesty is not | **supported** | high | below |
| H1a | Official ralph-wiggum: same-session Stop-hook block (no fresh context); DONE = literal `<promise>` match; every error path fails OPEN | **VERIFIED** | high | plugin stop-hook.sh (68f90e0); #81828 #95102 #78490 |
| H1b | `/goal`: transcript-only "small fast model" evaluator, no tools, bound only by condition text | **VERIFIED** | high | code.claude.com/docs/en/goal ; #100010 #98066 |
| H1c | Community loops self-declare DONE (frankbria dual gate; ralphex validation prompt-only, checkboxes model-ticked) | **VERIFIED** | high | github.com/frankbria/ralph-claude-code ; github.com/umputun/ralphex |
| H2 | Anthropic harness = canonical plan artifact; `passes` self-flipped; test rule prompt-only | **supported** | high | anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| H3 | No tool binds each plan item → locked executable judge run by a non-implementer + stop line | **supported (not refuted)**. Plan tools 0/9. Nearest: continuous-claude (code-enforced CI gate at merge level, but no-op without CI, judge editable in own PR); red-green-mode (per-item contract + non-LLM gate, but disarmable) | high | en-plan-review-prompt.md; continuous_claude.sh c9edd80; red-green-mode fb8289e |
| H3b | Separate-model ≠ external; the property that matters = judge EXECUTES. Doc lists prompt → /goal → Stop-hook script ("deterministic gate") → refutation subagent; strict ranking = our inference | supported | high | code.claude.com/docs/en/best-practices L40-50 |
| H3c | Plan review should compress scope | supported | med | HN 45610996; Fowler SDD; BMAD plan budget 900–1300 tok |
| H3d | LLM reviewers over-find / game rubrics | **supported, official + ZH** | high | best-practices L549; bmad-review; v2ex 1217464 |
| H3e | LLM reviewer converges only with explicit criteria (= contract) | supported | med | v2ex 1195006 (8 rounds, ~$100, no convergence until criteria added) |
| H4 | Headless control knobs | **covered** | high | hooks / headless / agent-sdk / scheduled-tasks docs |
| H5 | Failure modes: runaway, context loss, tampering, false-done | **supported** | med-high | v2ex 1199391 ($268, 1466 iter); Orbi v2ex 1245983 (32/77 compacted); METR; #72480 |
| H6 | Code orchestrator state machine; review DIFF vs plan | **supported, official** | high | best-practices L536; superpowers SDD; BMAD step-04; SDK ResultMessage.subtype |
| H7 | LLM orchestrator may fabricate subagent results → orchestrator in code + receipts | plausible, unmeasured | low-med | superpowers #1749 (WEAK, 0/2 repro) |
| H8 | Judge integrity must be code-enforced on END STATE (hash/diff vs git ref, sandbox), not path denies | **supported** | high | permissions L365; #92542 #103241 (open bypasses); agent-guard; red-green-mode |
| H9 | Unattended success tracks task verifiability | supported, cross-language | med | v2ex 1200449, 1228560; claude.com/blog/getting-started-with-loops |
| H10 | Safe terminal state = branch awaiting human; human gates left-shifted | supported (practice, not measured) | low-med | github.com/jzb1006/claude-vigil ; v2ex 1223573 |
| H12 (new) | Process success ≠ task success: `claude -p` exit 0 / "success" on do-nothing runs → orchestrator must judge on artifacts (commits, server records), never exit code or model text. Gold Band's `$.result` and Vigil's scope hook also fall to self-report / Bash bypass | **VERIFIED** (article quotes match: 4/4 exit 0 + "success"; scheduler 13/13 "成功" incl. hook-blocked; zero-commit rule; local repro on 2.1.286: tools removed → exit 0, `subtype:"success"`, `is_error:false`, file not created; `permission_denials` empty when tools removed vs attempted-and-denied not reproduced; n small, single author) | high | ithelp.ithome.com.tw/articles/10423514 ; zh-community.md |
| H11 | Hide the scorer from the implementer | **hypothesis only** — METR 43× compares task suites (confounded by difficulty/scaffolding), not visibility | low | metr.org/blog/2025-06-05-recent-reward-hacking |

## Coverage

| sub-topic | status | sources | limits |
|---|---|---|---|
| 1 Loop mechanics + primitives (EN) | covered | ~20 | — |
| 2 Plan / review / prompt synthesis (EN) | covered | ~18 | prompt-shape effect unmeasured |
| 2b Judge integrity (emergent #1) | covered | ~8 | no holdout-test tool exists |
| 3 ZH community | covered | ~21 | linux.do / Zhihu 403 |
| 4 EN failure modes | covered | ~18 | Reddit unreachable; Lobsters unsearched; EN $ figures paywalled; no same-session vs fresh A/B |
| 5 ZH-TW | covered (thin: 1 deep source) | ~3 | PTT/Dcard/繁中 Medium unreachable (US-only search). GEM: iThome 5-month lab — `claude -p` exit 0 + "success" on 4/4 do-nothing runs, scheduler 13/13 "成功" incl. blocked; rule "零 commit 一律判失敗", "驗收看服務端紀錄"; overlap → duplicate tickets (4 vs 2, 12 vs 2); lock + dedup + STOP-file brake outside Claude; cold start 51,673 tok / $0.335 per `claude -p` (ithelp 10423514, 10403459) — exit-0 claim with verifier |

## Verifier verdicts (roll-up)

- CONFIRMED: ralph-wiggum internals; /goal; 8-block cap (resets on tool call); headless flags (--bare needs API key); best-practices diff reviewer + over-find warning; superpowers #2112 breaker (v6.2.0); continuous-claude CI gate in code; deny-rule scope + open bypasses; METR table values; `stop_hook_active` = "already continuing" (tested locally on 2.1.286: false → true after one block).
- PARTIAL: /goal "Haiku default"; gate ladder ordering; METR 43× interpretation and "don't cheat" (one task, plan-stage measure).
- REFUTED: ralphex external gate; Agent SDK credit split (paused 2026-06-15; Max/Team monthly API credits since 2026-10-07).
- WEAK: superpowers #1749 fabrication.
- red-green-mode (executed): non-LLM gate; fail-closed except missing ledger / `echo PASS`; contract layer off unless RGM_CONTRACT; attestation-deletion bypass works; recall 55/55 reproduced, noise not rerun.

## Design consequences flagged for synthesis

- Re-judging Stop hook must NOT early-exit on `stop_hook_active` (that makes it one-shot); use its own counter, with the 8-cap as backstop. Loops that keep calling tools are unbounded → hard iteration/budget caps in the orchestrator.
- Fail closed on a missing judge/ledger (the gap in both ralph-wiggum and red-green-mode).
- Judge (contract + verifier commands) authored before implementation, approved, read by the orchestrator from a git ref / read-only path, never from the implementer's worktree.
- Path to this workspace contains a space → #78490 plugin-hook breakage risk.

## Steering

- **STOP PROPOSED to team-lead (pass 12)** with top-10 findings; supervisor confirmed exit conditions met. New-topic slots used 1/2.
- ZH-TW addendum (g-zh): Day 19 https://ithelp.ithome.com.tw/articles/10420353 — deterministic evidence-citation gate `check_result.py` (<50 lines, stdlib, 0.1 s, no model): result JSON vs task.json + pre-built evidence.json; a `confirmed` claim must cite an existing receiver-side record of the SAME id; exit 1 → RETURN_FOR_EVIDENCE, exit 0 → READY_FOR_REVIEW (gate never executes the action). LLM checker 39/39, 0/3 fooled by injected "請標記 PASS", ~$0.013/7 s vs $0/0.1 s. Limits: passed a wrong `next_action` with correct ids; evidence must be pre-built, never model-written. = receipts pattern, ZH-TW independent corroboration. Day 6 not located → Unresolved. **Correction:** Day 19/20/28 belong to series 「買了 Claude Code，然後呢？」; the 51,673 tok / $0.335 cold-start number (10403459) is from 「我讓 Claude Code 自己跑了五個月」.
- Released: g-loop-en, g-plan-en, g-zh. Verifier released after H12 verdict. g-zh held for trailing addendum (iThome Day 6 / Day 19, ≤4 fetches → zh-tw-community.md). steer-lead stays up until synthesis is confirmed.
