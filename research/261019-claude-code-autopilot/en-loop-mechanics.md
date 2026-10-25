# EN loop mechanics & official primitives (g-loop-en)

Scope: how to run headless Claude Code implementation sessions, judge them, loop until done. Date of gather: 2026-10-20. Tags: GEM / MEH / NOISE. Conf = confidence.

## TL;DR vs hypotheses

| Hyp | Status | One-line |
|---|---|---|
| H1 loop solved, termination honesty not | CONFIRMED + REFINED | Official plugin is NOT fresh-context (same session, same prompt re-fed). Fresh-context = Huntley bash loop. DONE in every mainstream variant is model-self-declared; the few external-judge designs are ralphex, continuous-claude, vercel `verifyCompletion` slot |
| H2 Anthropic harness = canonical plan-as-artifact | CONFIRMED | `feature_list.json` passes booleans, but the *model* flips them -> still self-grading; JSON chosen to resist tampering |
| H4 control knobs | CONFIRMED + NEW | Built-in `/goal` (prompt-Stop-hook w/ Haiku evaluator, works under `-p`) is missing from brief; `--permission-prompts none`, `--json-schema`->`structured_output`, `--bare` becoming default for `-p` |
| H6 orchestrator state machine > bash loop | SUPPORTED | SDK `ResultMessage.subtype`, `session_id`, `total_cost_usd`, `--resume` give the state-machine hooks; vercel `ralph-loop-agent` + ralphex show the shape |

## 1. Ralph Wiggum: origin, official plugin, variants

| Claim | Source | Tag | Conf |
|---|---|---|---|
| Original: `while :; do cat PROMPT.md \| claude-code ; done`; one thing per loop; spec + `@fix_plan.md` held constant each loop; 1 subagent only for build/test to avoid backpressure | https://ghuntley.com/ralph/ | GEM | high |
| Huntley failure modes: placeholder implementations, ripgrep non-determinism ("unimplemented" false conclusions), context quality degrading ~147-152k tokens, overnight loops leave unbuildable states needing `git reset` | https://ghuntley.com/ralph/ | GEM | high |
| Huntley claims: "6 repos shipped overnight" (YC hackathon), "$50k contract delivered for $297" - anecdotal, no method | https://ghuntley.com/ralph/ | MEH | med |
| Press: ~$10/hour compute for Ralph cloning commercial software | https://www.theregister.com/2026/01/27/ralph_wiggum_claude_loops/ | MEH | med |
| Official plugin `ralph-wiggum` (commands: ralph-loop, cancel-ralph, help; hooks/stop-hook.sh; scripts/setup-ralph-loop.sh) | https://github.com/anthropics/claude-code/tree/main/plugins/ralph-wiggum | GEM | high |
| Stop hook mechanics: reads `.claude/ralph-loop.local.md` (YAML frontmatter `iteration`, `max_iterations`, `completion_promise` + prompt body). If no file -> exit 0 (allow stop). If `max_iterations>0 && iteration>=max` -> delete state, allow. Else emits `{"decision":"block","reason":<SAME prompt text>,"systemMessage":"Ralph iteration N ..."}` exit 0. Increments iteration via sed | https://raw.githubusercontent.com/anthropics/claude-code/main/plugins/ralph-wiggum/hooks/stop-hook.sh | GEM | high |
| **Same session, same context**: command text says "You'll see your previous work in files and git history"; hook re-injects via `reason` inside the running session. Not fresh-context. Contradicts brief H1 phrasing "fresh `claude -p` per iteration" for the plugin | stop-hook.sh + https://raw.githubusercontent.com/anthropics/claude-code/main/plugins/ralph-wiggum/commands/ralph-loop.md | GEM | high |
| DONE detection = last assistant text message, first `<promise>...</promise>`, whitespace-normalised, literal `=` compare with `--completion-promise`. No external check. Prompt text tells model "ONLY when statement is TRUE - do not lie to exit!" | stop-hook.sh | GEM | high |
| No promise set => "loop runs infinitely" (only `--max-iterations` stops it); max_iterations=0 = unlimited | stop-hook.sh | GEM | high |
| Fail-open: corrupted state / missing transcript / no assistant text / jq failure -> `rm` state file and allow exit (loop silently ends, no false-done flag) | stop-hook.sh | GEM | high |
| Known bypass/bug: expected promise not whitespace-normalised, so a promise with double space can never match (unstoppable except max-iter) | https://github.com/anthropics/claude-code/issues/81828 | GEM | high |
| Bug: jq error handler unreachable under `set -e` -> stale state file | https://github.com/anthropics/claude-code/issues/95102 | MEH | high |
| Bug: stop-hook.sh missing exec bit on Linux (closed); Windows: bundled plugins' `.sh` hooks never run (open) | https://github.com/anthropics/claude-code/issues/38686 , https://github.com/anthropics/claude-code/issues/95673 | MEH | high |
| Bug: `${CLAUDE_PLUGIN_ROOT}` unquoted in plugin hooks.json breaks hooks when path has a space (macOS) - relevant: this repo's path has a space ("ambition skiill") | https://github.com/anthropics/claude-code/issues/78490 | GEM | high |
| Model can invoke `/ralph-loop` itself (frontmatter key `hide-from-slash-command-tool` unrecognised) | https://github.com/anthropics/claude-code/issues/79138 | MEH | high |
| Community critique: plugin "fundamental flaw: single context window... context bloat, hallucination risk"; recommends bash loop w/ fresh context + PRD + activity.md + screenshots | https://github.com/coleam00/ralph-loop-quickstart | GEM | med (opinion, 160 stars) |

### Top community variants (gh search, by stars)

| Repo | Stars | Judge / DONE mechanism | Source | Tag |
|---|---|---|---|---|
| frankbria/ralph-claude-code | 9709 (v0.11.5, 784 tests) | Dual-condition gate: heuristic completion indicators AND model's explicit `EXIT_SIGNAL: true`; circuit breaker; 100 calls/hr; `--resume <session_id>` (fixed "session hijacking" of `--continue`, #151); git backup branches; force-exit after 5 consecutive completion indicators. Changelog = failure catalogue: premature exit after 5 loops, `STATUS: COMPLETE`+`EXIT_SIGNAL:false` override (#146), checkbox regex counting dates as tasks (#144). Still model-declared | https://github.com/frankbria/ralph-claude-code | GEM | high |
| mikeyobrien/ralph-orchestrator | 3181 | not read | https://github.com/mikeyobrien/ralph-orchestrator | MEH | - |
| michaelshimeles/ralphy | 2974 | bash loop over PRD, multi-agent CLIs; not read in depth | https://github.com/michaelshimeles/ralphy | MEH | - |
| Th0rgal/open-ralph-wiggum | 1903 | wraps OpenCode/Claude/Codex; not read | https://github.com/Th0rgal/open-ralph-wiggum | MEH | - |
| umputun/ralphex | 1503 | plan.md with `## Validation Commands` (e.g. `go test ./...`) + `- [ ]` tasks; FRESH `claude --print` per task; auto-commit per task; then 5-agent -> codex -> 2-agent review pipeline; worktree isolation; Docker. Closest to "external judge + fresh session + review" | https://github.com/umputun/ralphex | GEM | high |
| AnandChowdhary/continuous-claude | 1386 | Per iteration: branch -> Claude commit -> PR -> wait on `gh pr checks` / reviews -> merge or close+discard; `SHARED_TASK_NOTES.md` handoff; stop when multiple agents say complete, or max-runs / cost / duration. Judge = CI | https://github.com/AnandChowdhary/continuous-claude | GEM | high |
| vercel-labs/ralph-loop-agent | 842 | AI-SDK outer loop with `verifyCompletion({result}) -> {complete, reason}`; `stopWhen: iterationCountIs/token/cost`; feedback injected into next iteration. Example check is `text.includes('DONE')` but slot accepts any external function. Experimental | https://github.com/vercel-labs/ralph-loop-agent | GEM | high |
| tzachbon/smart-ralph | 559 | spec-driven (plan front half) + Ralph; g-plan-en territory | https://github.com/tzachbon/smart-ralph | MEH | - |
| dial481/ralph | not in top results of `gh search repos ralph claude` | - | - | - | unresolved |

Observation: of the loops read, only ralphex (validation commands), continuous-claude (CI), and vercel's callback slot let a non-model process decide DONE. Everything else = string/flag the model emits.

## 2. Anthropic "Effective harnesses for long-running agents"

Source: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents (fetched).

| Claim | Tag | Conf |
|---|---|---|
| Two roles: initializer agent (first session only) writes `init.sh`, `claude-progress.txt`, initial git commit, feature list; coding agent in later sessions makes incremental progress with clean handoffs | GEM | high |
| `feature_list.json` entry shape: `{category, description, steps[], passes:false}`; JSON chosen over Markdown because model less likely to inappropriately edit it; instruction "It is unacceptable to remove or edit tests" | GEM | high |
| One feature per session; prevents "one-shotting" the app | GEM | high |
| Session start ritual: `pwd`, read git log + progress file, pick highest-priority failing feature, run `init.sh`, run basic e2e smoke test before new work | GEM | high |
| Verification via browser automation (Puppeteer MCP) as a user would, not just unit tests/curl. The agent still sets `passes` itself -> self-reported | GEM | high |
| Failure -> fix table: premature victory declaration -> feature list starts all-failing; buggy env -> git + progress notes; untested "done" -> e2e self-verify; setup time -> init.sh | GEM | high |
| Plan "review" is implicit via tests, no reviewer agent (H2 confirmed) | GEM | med |

## 3. `claude -p` flags that matter (docs fetched)

Sources: https://code.claude.com/docs/en/headless , https://code.claude.com/docs/en/cli-reference

| Flag / behaviour | Detail | New/changed | Tag |
|---|---|---|---|
| `--output-format text\|json\|stream-json` | json: result, session_id, usage, `total_cost_usd`, per-model breakdown. stream-json needs `--verbose`; last line = `result` message | - | GEM |
| `--json-schema '<schema>'` (print only) | validated output in `structured_output` field of json result; invalid schema -> exit with error; `format` keyword annotation only | newer; SDK result subtype `error_max_structured_output_retries` | GEM |
| `--max-turns N` (print only) | "Exits with an error when the limit is reached", no default limit; counts tool-use turns | - | GEM |
| `--max-budget-usd` (print only) | client-side estimate, can overshoot by one response + running subagents; blocks new subagents (`Budget limit reached`) and stops bg subagents (v2.1.217+); totals restored by `--resume` do NOT count toward the cap | v2.1.217 behaviours | GEM |
| `--resume <id\|name\|path.jsonl>`, `--continue`, `--fork-session`, `--session-id <uuid>` | `claude -p --continue` includes -p/SDK sessions (plain `--continue` skips them). Cost totals accumulate across resumes | resume by transcript path new | GEM |
| `--no-session-persistence` | print only; no resume possible | - | MEH |
| `--append-system-prompt[-file]`, `--system-prompt[-file]` | system prompt is recorded on first request and reused on resume until compaction; `--system-prompt-snapshot off` rebuilds each request (v2.1.257+). Gotcha for loops that tweak prompts across `--resume` | v2.1.257, v2.1.283 | GEM |
| `--allowedTools` / `--disallowedTools` / `--tools` | `--allowedTools` auto-approves; `--tools` restricts availability; scoped rules `Bash(git diff *)` (space before `*` matters) | - | MEH |
| `--permission-mode default\|acceptEdits\|plan\|auto\|dontAsk\|bypassPermissions` | A `-p` run with nothing set takes built-in start mode which "can be `auto`" - pass explicitly. `dontAsk` = deny anything not pre-allowed (locked-down CI). `auto` = classifier | auto mode newer | GEM |
| `--permission-prompts none` | print only; denies unresolvable prompts and tells model not to retry; removes AskUserQuestion | v2.1.259+ | GEM |
| `--bare` | skips hooks, skills, plugins, MCP, auto memory, CLAUDE.md; needs `ANTHROPIC_API_KEY` (no OAuth/keychain); "recommended for scripted calls, will become default for -p". Before v2.1.286 limits only partly held | v2.1.286 | GEM |
| `--setting-sources user,project,local` | choose which settings load; note: without `--bare`, `-p` runs project hooks and `.mcp.json` servers even in untrusted folders | - | GEM |
| `--settings <file\|json>`, `--agents <json\|file>` (file form v2.1.281), `--append-subagent-system-prompt` (v2.1.205) | inject per-run config/agents | newer | MEH |
| `--init-only`, `--init`/`--maintenance` (Setup hooks) | run SessionStart/Setup hooks only | - | MEH |
| `--worktree/-w`, `--bg`(not with -p), `--fallback-model`, `--effort low..max\|ultracode`, `--restricted` (eval harness mode) | `--restricted` explicitly designed for "evaluation harness drives claude on a shared machine" | v2.1.248 | MEH |
| Exit/ops: exit 0 success, non-zero on failure; SIGTERM -> exit 143, no result recorded; `-p` waits up to 10 min idle for background work (`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`) | - | GEM |
| Stream events useful for receipts: `system/init` (plugins, mcp_servers, `plugin_errors`, `mcp_server_errors`), `system/api_retry`, `permission_denied`, result `permission_denials`; `--include-hook-events`; `--forward-subagent-text` (v2.1.211) so subagent tool_use shows up in transcript | many v2.1.2xx | GEM |
| BILLING (unverified at primary): ralphex README and press say from 2026-06-15 `claude -p`/Agent SDK/claude-code-action on subscriptions draw from a separate monthly "Agent SDK credit" (~$20 Pro / $100 Max5x / $200 Max20x, no rollover). Official costs page fetched does not mention it. https://github.com/umputun/ralphex , https://www.infoworld.com/article/4171274/anthropic-puts-claude-agents-on-a-meter-across-its-subscriptions.html | GEM | med |

## 4. Hooks as loop control

Source: https://code.claude.com/docs/en/hooks , https://code.claude.com/docs/en/hooks-guide

| Claim | Tag | Conf |
|---|---|---|
| Stop stdin: common fields + `last_assistant_message`, `stop_hook_active`, `transcript_path`, `permission_mode`. SubagentStop adds `agent_id`, `agent_type` | GEM | high |
| Block a stop: exit 2 (stderr = reason fed back) OR stdout JSON `{"decision":"block","reason":"..."}`. `continue:false` halts Claude entirely. `hookSpecificOutput.additionalContext` feeds context without blocking | GEM | high |
| **Block cap**: Claude Code overrides a Stop hook after 8 consecutive blocks with no tool call in between; script should check `stop_hook_active` and exit 0 | GEM | high |
| Hook types: command, http, mcp_tool, prompt, agent. Prompt/agent Stop hooks return `{"ok":true}` / `{"ok":false,"reason":"..."}`. Agent hook (experimental): subagent with Read/Grep/tools, 60 s default timeout, up to 50 tool turns - can run the test suite as judge | GEM | high |
| PreToolUse: `hookSpecificOutput.permissionDecision` allow/deny/ask/defer + `updatedInput`; exit 2 blocks and cannot be overridden by JSON allow. Usable to forbid edits to test/judge paths (anti test-tampering) | GEM | high |
| SessionStart matchers startup/resume/clear/compact/fork; command and mcp_tool only | MEH | high |
| `onFailure: "block"` field (v2.1.295+); hooks output capped 10,000 chars | MEH | med |
| Stop-hook loops have real breakage: infinite loop when final step needs user-only auth (hundreds of rounds, #100010), classifier-denied `gh pr merge` re-fires ~15x (#98066), bills full turn while bg agent mid-write (#93745), git-check hook false positive on SSH-signed commits = unbreakable loop (#69201) | GEM | high |
| Gotcha: hooks in a project's settings run under `-p` even in untrusted folders unless `--bare` | GEM | high |

URLs: https://github.com/anthropics/claude-code/issues/100010 , /98066 , /93745 , /69201

## 5. Built-in `/goal` (missing from brief)

Source: https://code.claude.com/docs/en/goal

| Claim | Tag | Conf |
|---|---|---|
| `/goal <condition>` = session-scoped prompt-based Stop hook. After each turn the "small fast model" (Haiku by default; `ANTHROPIC_DEFAULT_HAIKU_MODEL` overrides - side effect: also changes the `haiku` alias everywhere) returns not-met / met / impossible + reason | GEM | high |
| Evaluator "does not call tools... can only judge what Claude has already surfaced in the conversation". => LLM reading the worker's own transcript. Separate model, but still transcript-judged, not an outside check | GEM | high |
| Works headless: `claude -p "/goal ..."` runs loop to completion in one invocation; use `--output-format stream-json --verbose` or it looks hung | GEM | high |
| Condition up to 4,000 chars; bound runs only via a clause in the condition ("or stop after 20 turns") judged by the evaluator - no hard cap flag | GEM | high |
| Stops loop itself if model makes no tool use for several turns; clears goal on auth failure, exhausted credit, context overflow not fixed by compaction, unavailable model; 3 auto-retries then pause on transient errors | GEM | high |
| Goal restored on resume (turn count/timer reset). Disabled when `disableAllHooks` or `allowManagedHooksOnly` | MEH | high |
| Anthropic compares: /goal vs /loop vs Stop hook; own Stop hook "can run a script for deterministic checks" | GEM | high |
| Anthropic blog "Loop engineering": 4 loop kinds (turn, goal, time, proactive); "A reviewer with fresh context is less biased"; "the more quantitative the checks, the easier to self-verify" | MEH | med | https://claude.com/blog/getting-started-with-loops |

## 6. Agent SDK as orchestrator

Source: https://code.claude.com/docs/en/agent-sdk/agent-loop (fetched)

| Claim | Tag | Conf |
|---|---|---|
| `query({prompt, options:{allowedTools, settingSources, maxTurns, maxBudgetUsd, effort, permissionMode}})` yields SystemMessage(init, session_id) ... ResultMessage | GEM | high |
| `ResultMessage.subtype`: `success`, `error_max_turns`, `error_max_budget_usd`, `error_during_execution`, `error_max_structured_output_retries`; all carry `total_cost_usd`, `usage`, `num_turns`, `session_id` -> clean state-machine inputs; `result` only on success | GEM | high |
| Single-shot `query()` raises after yielding an error result; wrap in try. Budget cap can overshoot by up to one response + running subagents | GEM | high |
| Resume restores full prior context (files read, actions); fork-session to branch. `sessionStore` adapter mirrors transcripts for stateless hosts | MEH | high |
| Hooks in SDK are in-process callbacks: PreToolUse, PostToolUse, Stop, SubagentStart/Stop, PreCompact (TS has more events than Python) | GEM | high |
| Subagents start with fresh context; only final message returns to parent -> keeps orchestrator context lean | GEM | high |
| Official/community plan->implement->verify loop examples: ralph-loop-agent (verifyCompletion), ralphex (plan + validation commands + review phases), continuous-claude (CI judge). No official Anthropic sample found beyond harness post | MEH | med |

## 7. Other primitives (one para each)

- **claude-code-action** (https://code.claude.com/docs/en/github-actions , repo https://github.com/anthropics/claude-code-action): GitHub Action v1; interactive mode (`@claude` mentions) vs automation mode (`prompt` input, any event incl. cron). Passes CLI args via `claude_args` (`--max-turns`, `--allowedTools`, `--model`). Built on Agent SDK; refuses bot actors unless `allowed_bots`; commits made with default `GITHUB_TOKEN` don't trigger CI. Natural fit for "judge = CI on a PR". Cost controls: `--max-turns`, workflow timeouts, concurrency. Tag GEM, high.
- **/loop skill** (https://code.claude.com/docs/en/scheduled-tasks): session-scoped; fixed interval (min 1 min, cron) or self-paced (model picks 1 min-1 h, ends via `ScheduleWakeup stop:true`; fallback wakeup ~20 min if iteration neither reschedules nor stops); recurring tasks expire after 7 days; max 50 tasks; fires only while idle. Under `-p`, self-paced wakeups keep the run open. Time-based, not completion-based - wrong tool for "until all items pass" except as a babysitter. Tag MEH, high.
- **Routines / cloud scheduled** (same page + https://code.claude.com/docs/en/routines): cloud, no machine needed, fresh clone, min interval 1 h, triggers by schedule/API/GitHub events. Desktop scheduled tasks: local, min 1 min. For event-driven proactive loops, not inner implement/judge loop. Tag MEH, high.
- **Workflow tool / dynamic workflows** (https://code.claude.com/docs/en/workflows): JS script run by a runtime; `agent()`, `parallel()`, `pipeline()`, `phase()`, `log()`, `args`; `schema` option forces structured JSON per agent (5 retries, `MAX_STRUCTURED_OUTPUT_RETRIES`); script holds loop + intermediate state, so orchestrator context stays small (this is H6 as a product); resumable within session via replay cache; limits: 16 concurrent agents default (env up to 256), 1000 agents/run, 4096 items per fan-out; no mid-run user input; no direct fs/shell from script; `Date.now()/Math.random()` throw. Works under `-p`/SDK but needs `Workflow` allow rule (or auto/bypass mode); `ultracode` keyword does NOT trigger from `-p`. Example prompt documented: "keep fixing until a check passes or two rounds in a row make no progress". Cannot span sessions (resumable only same session). Tag GEM, high.
- **Agent teams / agent view / `--bg`**: not in scope; `--bg` incompatible with `-p`. Tag NOISE for this thread.

## Elite-forum evidence (EN)

| Claim | Source | Tag | Conf |
|---|---|---|---|
| HN user ran Ralph loops with Claude Code 6 months before Feb 2026: "More often than not, it ended up exhibiting crazy behavior even with simple project prompts" - tasks drifted (tried to publish to npm/pypi) | https://news.ycombinator.com/item?id=47083624 | GEM (scope drift, anecdote) | med |
| HN: "Continuous agents and what happens after Ralph Wiggum?" - top replies challenge security of generated auth; no judge discussion | https://news.ycombinator.com/item?id=46632445 | MEH | med |
| HN comment: "Remember 'prompt engineering'? Remember 'Ralph loops'?" - skepticism that loop workflows stay relevant | https://news.ycombinator.com/item?id=50064082 | MEH | low |
| HN comment (GPT-5.5 thread): "/ralph-loop plugin works well to keep the model hammering at the task" - positive, no numbers | https://news.ycombinator.com/item?id=47881879 | NOISE | - |
| Reddit r/ClaudeCode, r/ClaudeAI: `site:` WebSearch returned nothing from reddit; Reddit inaccessible via this route (parallax reddit tools not tried). Lobste.rs not searched | - | - | - |

Honest gap: forum evidence on loop failure is thin; HN Algolia API gave story/comment hits but few with numbers. Wave-2 (en-failure-modes) should mine r/ClaudeCode via parallax + github issues.

## Contradictions

1. Brief H1 says official ralph-wiggum = "fresh `claude -p` per iteration". Source says otherwise: Stop hook re-injects same prompt in the SAME session (context accumulates, auto-compaction applies). Fresh context per iteration is Huntley's bash loop and ralphex/continuous-claude/frankbria. https://raw.githubusercontent.com/anthropics/claude-code/main/plugins/ralph-wiggum/hooks/stop-hook.sh
2. Anthropic says `/goal` completion is "decided by a fresh model rather than the one doing the work" (separate-evaluator framing), but the evaluator sees only the worker-produced conversation and runs no tools. Independent *model*, not independent *evidence*. https://code.claude.com/docs/en/goal
3. Harness post uses a `passes` boolean to resist premature victory, but the same coding agent that implements the feature also sets `passes: true` after its own e2e test; protection is a prompt rule + file format, not enforcement. https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
4. Docs: `--max-budget-usd` "Stop the run once spend reaches this amount" vs. headroom note: can pass cap by one response + subagents; and resumed totals don't count toward it -> a loop of `--resume` calls each gets a fresh cap. https://code.claude.com/docs/en/cli-reference
5. `--bare` "recommended for scripted calls" but needs API key (no OAuth) while billing notes say subscription -p usage moves to Agent SDK credit -> subscription-based unattended loops constrained either way (billing claim unverified at primary).

## Unresolved

- dial481/ralph not found by `gh search repos ralph claude`; need direct lookup or drop.
- mikeyobrien/ralph-orchestrator, ralphy, open-ralph-wiggum: mechanisms not read (stars-ranked only).
- Agent-hook Stop judge: does `ok:false` on Stop reuse the 8-block cap? Not verified.
- Agent SDK Stop hook callback contract (TS/Python) not fetched (https://code.claude.com/docs/en/agent-sdk/hooks).
- Agent SDK credit billing change: official source not found; confirm via verifier.
- Does `--max-turns` hit return exit code non-zero AND a result JSON with `subtype: error_max_turns` under `-p --output-format json`? Docs say "exits with an error"; SDK doc lists subtype. Likely yes, untested.
- Real measured loop numbers (iterations to done, $/loop, false-done rate): none found in primary sources. Only anecdotes (Huntley $297, Register $10/h).
- Reddit/Lobste.rs evidence not gathered.
- `/goal` under `-p` + a `Stop` command hook running tests: combined behaviour and interaction with the 8-block cap untested.

## Sources
- https://ghuntley.com/ralph/
- https://github.com/anthropics/claude-code/tree/main/plugins/ralph-wiggum
- https://raw.githubusercontent.com/anthropics/claude-code/main/plugins/ralph-wiggum/hooks/stop-hook.sh
- https://raw.githubusercontent.com/anthropics/claude-code/main/plugins/ralph-wiggum/commands/ralph-loop.md
- https://github.com/anthropics/claude-code/issues/81828 , /95102 , /38686 , /95673 , /78490 , /79138 , /100010 , /98066 , /93745 , /69201
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- https://code.claude.com/docs/en/headless , /cli-reference , /hooks , /hooks-guide , /goal , /workflows , /scheduled-tasks , /github-actions , /costs , /agent-sdk/agent-loop
- https://claude.com/blog/getting-started-with-loops
- https://github.com/frankbria/ralph-claude-code , https://github.com/umputun/ralphex , https://github.com/AnandChowdhary/continuous-claude , https://github.com/vercel-labs/ralph-loop-agent , https://github.com/coleam00/ralph-loop-quickstart
- https://news.ycombinator.com/item?id=47083624 , 46632445 , 50064082 , 47881879
- https://www.theregister.com/2026/01/27/ralph_wiggum_claude_loops/
- https://www.infoworld.com/article/4171274/anthropic-puts-claude-agents-on-a-meter-across-its-subscriptions.html
