# Loop Primitives: What Exists and What to Use

Every primitive here was read at source or docs level. "Verified" means the verifier checked it independently ([verifier-log.md](verifier-log.md)).

## Official

| Primitive | Mechanics (verified) | Use for | Avoid because |
|---|---|---|---|
| `ralph-wiggum` plugin ([source](https://github.com/anthropics/claude-code/tree/main/plugins/ralph-wiggum)) | Stop hook re-feeds the SAME prompt in the SAME session; done = literal match of the first `<promise>` in the last assistant message; state in `.claude/ralph-loop.local.md`; `max_iterations 0` = unlimited; every error path deletes state and allows exit (fail open); a tool-only last turn ends the loop silently; not session-scoped | Interactive nudging | Context accumulates; no outside check; fails open; a double-space promise never matches (#81828); a space in the plugin path breaks hooks (#78490, this workspace path has one) |
| `/goal <condition>` ([docs](https://code.claude.com/docs/en/goal)) | Session-scoped prompt Stop hook; a "small fast model" reads the transcript and returns met, not met, or impossible; runs no tools; works as `claude -p "/goal ..."`; bounded only by a turn clause in the condition text | Cheap babysitter for a bounded chore | Judge sees only what the worker said; hundreds of rounds when the last step needs a human (#100010); about 15 re-fires after a permission denial (#98066) |
| Stop hook, command type ([docs](https://code.claude.com/docs/en/hooks)) | Exit 2 or `{"decision":"block","reason":...}` blocks the stop and feeds the reason back; Claude Code overrides after 8 consecutive blocks with NO tool call between, and tool calls reset the count; `stop_hook_active` means "already continuing": false on the first stop, true after one block (tested on 2.1.286) | The inner loop: run the item's judge, block with its output | One-shot if the script exits on `stop_hook_active`; unbounded if the model keeps calling tools; editable by the agent unless installed from outside the repo |
| Stop hook, agent type (experimental) | Subagent with tools, 60 s default timeout, up to 50 tool turns, returns `{"ok": ...}` | A judge that can run tests without a shell script | Still an LLM verdict; cap interaction untested |
| PreToolUse deny, `Edit(tests/**)` | Covers built-in file tools and recognized Bash file commands | First layer only | Not scripts that open files; open bypasses #92542, #103241; the sandbox is the OS-level answer |
| Agent SDK `query()` ([docs](https://code.claude.com/docs/en/agent-sdk/agent-loop)) | `ResultMessage.subtype` success / error_max_turns / error_max_budget_usd / error_during_execution / error_max_structured_output_retries; `session_id`, `total_cost_usd`, `num_turns`; in-process hooks; resume and fork | The orchestrator, when in-process hooks are wanted | No default turn or budget limit; budget overshoots by one response |
| `claude -p` flags ([headless](https://code.claude.com/docs/en/headless)) | See [contract-and-prompt.md](contract-and-prompt.md) | The implementation session | `--bare` needs an API key |
| Workflow tool ([docs](https://code.claude.com/docs/en/workflows)) | JS script with `agent()`, `parallel()`, `pipeline()`, schema-forced output, replay cache | In-session multi-agent steps such as a plan lint by agents | Cannot span sessions; no filesystem or shell from the script |
| `/loop`, routines, scheduled tasks | Time-based re-fire; routines run in the cloud on a fresh clone, minimum interval 1 h | Triggering a run | Time-based, not completion-based; the Desktop scheduler logged blocked runs as success (iThome) |
| claude-code-action | Automation mode, passes CLI args, refuses bot actors | Judge = CI on a PR | Commits made with the default `GITHUB_TOKEN` do not trigger CI |

## Community loops, by stars

| Tool | Done decided by | Fresh context | Verified note |
|---|---|---|---|
| snarktank/ralph 22k | agent sets `passes: true` in `prd.json` | per iteration | static prompt; the agent picks the story |
| frankbria/ralph-claude-code 9.7k | heuristics AND the model's `EXIT_SIGNAL`; circuit breaker on git progress stops runaway, not false done | per iteration | changelog lists premature exits; file protection covers its own files, not tests |
| umputun/ralphex 1.5k | model ticks `[x]` and emits a done signal; Go only checks no `[ ]` remain | per task `claude --print` | **refuted**: the `## Validation Commands` section is never run by the Go code; README overstates |
| AnandChowdhary/continuous-claude 1.4k | shell merges on all-green `gh pr checks`, closes on red | per iteration | **confirmed** code gate; no checks = pass; agent runs with permissions skipped and can edit tests and workflows in its own PR; one of max-runs, max-cost, max-duration required |
| vercel-labs/ralph-loop-agent 842 | `verifyCompletion({result})` slot, any function | per iteration | example check is `text.includes('DONE')` |
| hidevinliu/red-green-mode 11 | non-LLM gate script, fail-closed Stop hook, SHA-256 lock | gate only | **executed by the verifier**: no model call in the gate; 55 of 55 hand-written cheats blocked at 12.7% false blocks (agent profile); disarmed by deleting the ledger; contract layer off unless `RGM_CONTRACT` is set; author rates unattended ops 3 of 10 |
| jzb1006/claude-vigil (ZH) | never auto-merge; branch awaits a human; `--budget-tokens`, `--budget-cost` | per task worktree | PreToolUse scope hook covers Edit and Write only; Bash bypasses it |
| diodeme/Gold-Band (ZH) | `$.result == true` over the agent's own JSON | per node | self-report; the author names the problem "both player and referee" |

## Pick

Orchestrator in code, fresh `claude -p` per item, command Stop hook as the inner loop, end-state judge from a ref. Read red-green-mode for the gate and continuous-claude for the merge logic.

## Related

[architecture.md](architecture.md) · [judge-integrity.md](judge-integrity.md) · [evidence.md](evidence.md) · raw: [en-loop-mechanics.md](en-loop-mechanics.md)
