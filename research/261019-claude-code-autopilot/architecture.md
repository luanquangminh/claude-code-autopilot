# Recommended Pipeline Architecture

One orchestrator in code drives a state machine over a locked plan contract. The model does two jobs inside it: draft the plan, and implement one item in a fresh session. Everything that decides is code.

## Stages

| # | Stage | Who runs it | Decides with |
|---|---|---|---|
| 1 | Plan draft | `claude -p` planning session (ambition brief or plan mode) | model writes; nothing is decided |
| 2 | Plan lint | orchestrator | every item has a judge command that exists and is RED on the baseline; scope paths exist; no item's scope touches judge paths |
| 3 | Plan review | fresh read-only LLM reviewer, 1 to 2 rounds, then human (or auto-mode pre-approval of the literal scope) | approval locks the contract; the reviewer cuts scope and flags requirement gaps only |
| 4 | Lock | orchestrator | commit contract and judge files to `refs/contract/<id>`, record a SHA-256 per item |
| 5 | Prompt | orchestrator builds a per-item brief | template in [contract-and-prompt.md](contract-and-prompt.md) |
| 6 | Implement | fresh `claude -p` in a worktree, hard caps | model works; emits a structured self-report that is treated as claims |
| 7 | Judge | orchestrator, from the ref, on the end state | judge exit code and output; tamper diff; receipts; zero commits = fail |
| 8 | Diff review (optional) | fresh reviewer, diff plus contract only | correctness and requirement gaps; anything outside scope goes to Unapproved |
| 9 | Loop control | orchestrator | attempts <= stop line; no-progress detector; global caps; STOP file; lock file |
| 10 | Report | orchestrator, one model call to prose it | ambition plan-vs-actual table; branch left for a human; never auto-merge |

## Why each choice

- **Code orchestrator, not a bash loop and not an LLM.** The SDK result carries `subtype` (success, error_max_turns, error_max_budget_usd, ...), `session_id`, `total_cost_usd`, `num_turns`, `permission_denials`: the state-machine inputs ([agent-loop docs](https://code.claude.com/docs/en/agent-sdk/agent-loop)). An LLM orchestrator can fabricate subagent results (superpowers #1749, unreproduced but plausible) and its context grows (resumed implementers reached 300k+ tokens, superpowers #2551). Anthropic's own recipe reviews the diff against the plan in a fresh subagent ([best-practices](https://code.claude.com/docs/en/best-practices)).
- **Fresh session per item.** Orbi: 32 of 77 sessions compacted at 131K and lost file reads and test output ([v2ex 1245983](https://www.v2ex.com/t/1245983)). Huntley: quality degrades near 150k tokens ([ghuntley.com/ralph](https://ghuntley.com/ralph/)). One feature per session is the harness post's rule. No A/B exists; this is consensus, not measurement.
- **Judge red before green.** A judge that already passes on the baseline is vacuous. That is red-green-mode's admitted root hole: the verifier is written by the party being judged, so `echo PASS` gets through.
- **Judge read from a ref, never from the worktree.** Deny rules do not cover scripts that open files, and two bypass issues are open ([permissions](https://code.claude.com/docs/en/permissions), #92542, #103241). Checking the end state makes the write path irrelevant. Details in [judge-integrity.md](judge-integrity.md).
- **Never trust the exit code or the model's text.** `claude -p` returned exit 0 and "success" on 4 of 4 do-nothing runs, and a scheduler logged 13 of 13 runs as success including blocked ones ([iThome Day 28](https://ithelp.ithome.com.tw/articles/10423514)). The verifier reproduced it on 2.1.286: with write tools removed, `claude -p "create x.txt"` exited 0 with `subtype: success` and no file. Claude asserted "tests passed" with no tool output (#72480). Receipts: every command the self-report claims must appear as a Bash `tool_use` in the stream-json transcript (ambition's `receipts.py`). The same idea, built independently: a 50-line stdlib script that passes a result only if it cites a record in an evidence file the model never writes ([iThome Day 19](https://ithelp.ithome.com.tw/articles/10420353)).
- **Zero commits = fail.** A dispatcher exited 0, was billed, and produced no commit; the author's rule ever since (iThome Day 28).
- **Hard caps in code.** The Stop-hook 8-block cap resets on every tool call, so a loop that keeps running checks is unbounded (#100010, hundreds of rounds). An uncapped Stop-hook loop ran 1,466 iterations for about $268 ([v2ex 1199391](https://www.v2ex.com/t/1199391)). continuous-claude requires one of max-runs, max-cost or max-duration in code.
- **Reviewers need a contract.** A Claude-writes, Codex-reviews loop ran 8 rounds at about $100 and never converged until the author supplied explicit criteria ([v2ex 1195006](https://www.v2ex.com/t/1195006)). A reviewer prompted for gaps "will usually report some, even when the work is sound" (best-practices). BMAD's "at least 10 findings" quota manufactures findings. So: criteria = the contract, severity tiers, 1 to 2 rounds, and a duty to cut scope (Kiro turned a small bug into 4 stories and 16 criteria, [HN](https://news.ycombinator.com/item?id=45610996)).
- **Honest miss, then move on.** After the stop line the item is recorded with the smallest real attempt, the measured gap and the blocker (ambition rule). A missed item never blocks the run.
- **End on a branch.** Vigil's rule: letting an unattended agent auto-merge is the shortcut to losing system trust ([v2ex 1214573](https://www.v2ex.com/t/1214573)). continuous-claude's agent can edit tests and workflows inside its own PR; only branch protection stops it.

## Inner loop inside one session (optional)

A command-type Stop hook that runs the item's judge and blocks with the output as the reason gives the model several tries before the orchestrator re-judges. Rules from the evidence: fail closed when the judge is missing; keep your own counter and ignore `stop_hook_active`, because a hook that exits on it judges once (tested on 2.1.286); treat the 8-block cap only as a backstop; install the hook from outside the worktree, since a hook inside the repo is editable (annyang's `check-on-stop.sh`). The experimental agent-type Stop hook can run tests too, but its verdict is an LLM's.

## What ambition-skill already gives you

| Need | Already in the repo |
|---|---|
| Contract format (Judge, Target, Stop line, Scope, Runs) | `skills/ambition/SKILL.md` |
| Honest-miss rule and plan-vs-actual report | same |
| Receipts check against the transcript | `evals/receipts.py` |
| Judged headless runner with caps and allowlist | `evals/run-all.sh` |
| Auto-mode pre-approval of the literal scope only | SKILL.md step 4 |
| Blind LLM judging of pipeline variants | `evals/judge/` |
| Eval cases that double as pipeline tests | `a-honest` (test contradicts spec), `a2-speed` (impossible target), `b-scope`, `e2-auto` |

Missing: the per-item state machine, the plan lint, the end-state tamper checks, the no-progress detector, the lock and STOP brake.

## Build order

1. `plan.json`, plan lint, lock ref. Verify: lint rejects a plan whose judge is green on the baseline.
2. One-item runner: fresh `claude -p`, judge from the ref, receipts, zero-commit rule. Verify: the `a-honest` fixture ends as an honest miss with tests untouched.
3. Loop, caps, honest miss. Verify: an impossible item (`a2-speed`) stops at its stop line and the run continues.
4. Diff review, report, branch. Verify: the `b-scope` fixture reports the README TODO as Unapproved or Next rung.
5. Blind-judge two pipeline variants with `evals/judge/`.

## Related

[overview.md](overview.md) · [contract-and-prompt.md](contract-and-prompt.md) · [loop-primitives.md](loop-primitives.md) · [judge-integrity.md](judge-integrity.md) · [evidence.md](evidence.md)
