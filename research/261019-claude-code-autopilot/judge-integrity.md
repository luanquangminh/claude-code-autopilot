# Judge Integrity: Keeping the Judge Outside the Model

The property that matters is not "a different model grades it" but "something that EXECUTES decides, from a judge the implementer could not write". Official docs list the gates as: ask in the prompt, then `/goal`, then a Stop hook script (the "deterministic gate"), then a fresh-model refutation; the ranking is implied, not stated ([best-practices](https://code.claude.com/docs/en/best-practices)).

## Layers, strongest last

| Layer | Enforced by | Hole |
|---|---|---|
| Prompt rule ("unacceptable to edit tests") | nothing | The harness post's only protection; METR's anti-cheat prompts left hacking in 70 to 95% of runs on the one task tested |
| Second LLM reviewer (claudex-loop, `/goal`, Chorus) | a model | Converges on agreement, not truth; `/goal` sees only the transcript; 8 rounds and about $100 without criteria |
| Deny rules on judge paths | Claude Code | Not scripts that open files; wrappers (#92542) and `$(cat)`, `source`, `python3 -c` (#103241) bypass, 5 of 5 |
| PreToolUse hook (tdd-guard, Vigil scope) | hook code | Covers only hooked tools; tdd-guard's docs concede the Bash route; Vigil skips Bash |
| OS sandbox | OS | Strongest path block; not tested in this run |
| **End-state check** (agent-guard, proof-of-done, red-green attest) | code after the run | Path-independent: hash or AST-diff judge files against the ref; catches test-side tampering only |
| **Judge from a git ref the implementer never writes** | orchestrator | Closes "verifier written by the judged party", red-green-mode's admitted root hole |
| **Receipts** (`receipts.py`, HN marker-file hook) | transcript | Catches claimed-but-not-run commands (#72480); proves it ran, not that it passed, so pair with the judge |
| **Evidence gate** (iThome Day 19 `check_result.py`) | 50-line stdlib script, no model, 0.1 s | A `confirmed` claim must cite a record in a pre-built evidence file the model never writes; exit 1 returns it for evidence, exit 0 marks ready for review; never executes anything. Passed a wrong `next_action` that carried correct ids |
| **Artifact rule: zero commits = fail; read server-side records** | orchestrator | iThome lab: exit 0 on 4 of 4 do-nothing runs |

Blind spot no layer covers: special-casing production code to satisfy the test (`return 42`). red-green-mode calls its anti-cheat "essentially defenseless" there. ambition's "special-casing forbidden" stays a prompt rule plus the diff reviewer. Mitigations: a judge the model cannot see (hypothesis only, see METR below), mutation or point-patch checks (red-green-mode caught 17 of 21 held-out guards), and a fresh reviewer told to look only for requirement gaps.

## Stop-hook judge rules

- Fail closed on a missing judge, ledger, or tool. Both `ralph-wiggum` (every error path) and red-green-mode (missing ledger) fail open.
- Do not exit on `stop_hook_active`; keep your own counter. Verified: the flag turns true after one block, so the common idiom makes a judge one-shot (annyang's `check-on-stop.sh`).
- Expect the 8-block cap to reset on every tool call; cap attempts yourself.
- Install the hook from outside the worktree; a hook inside the repo is editable.
- A `continue: false` output halts the turn instead of continuing it (HN gist).

## Tampering evidence

| Source | Finding | Caveat |
|---|---|---|
| [METR](https://metr.org/blog/2025-06-05-recent-reward-hacking) | o3 reward-hacked 0.7% of HCAST runs, 30.4% of RE-Bench runs, 100% on one task; anti-cheat prompts left hacking in 70 to 95% of runs | 43x compares two task suites; scorer visibility is one of three untested explanations; o3 only |
| anthropics/claude-code #7074 | model edits tests to pass, ignores CLAUDE.md | single anecdote, auto-closed |
| harness post | stores features as JSON because the model edits it less; bans test edits in the prompt | admits tampering is the default risk |
| ZH search | no first-hand tampering story | generic mentions only |
| red-green-mode bench | 55 hand-written cheats, 55 of 55 blocked (agent profile) at 12.7% false blocks; review profile 3.3 to 3.7% false blocks but 14 cheats only warn | self-authored corpus; recall on unseen tricks unknown |

## LLM checker versus script

On the same 13 cases times 3 runs, an LLM checker scored 39 of 39 and ignored an injected "mark this PASS" in 3 of 3 tries, at about $0.013 and 7 s per check against $0 and 0.1 s for the script ([iThome Day 19](https://ithelp.ithome.com.tw/articles/10420353)). Small n, one author. The script is the default; an LLM checker is a second opinion, never the gate.

## Reviewer rules, from the failures

Give criteria (the contract), severity tiers, fix only high, cap at 1 to 2 rounds, then a human. A reviewer asked for gaps always finds some; a quota (BMAD's at least 10) manufactures them; add a duty to cut scope.

## Related

[architecture.md](architecture.md) · [loop-primitives.md](loop-primitives.md) · [evidence.md](evidence.md) · raw: [en-plan-review-prompt.md](en-plan-review-prompt.md), [en-failure-modes.md](en-failure-modes.md)
