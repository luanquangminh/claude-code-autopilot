# Research Brief: Claude Code Autopilot Pipeline

Shared context for the research team. Every teammate reads this first.

## Goal (the researchable question)

How should one build an automation pipeline on Claude Code that:
1. auto-generates an implementation plan from a task,
2. reviews/critiques that plan before work starts,
3. synthesizes a per-task prompt,
4. launches a headless implementation session (`claude -p` / Agent SDK),
5. judges the result with something OUTSIDE the model, and
6. loops (fresh session) until every plan item passes — honestly, without the model grading its own work or gaming the judge.

Deliverable: a cited report mapping existing approaches, their measured failure modes, and a recommended architecture.

## Ground truth already read: samhvw8/ambition-skill (v0.4.0)

| Mechanism | What it does | Why it matters to the pipeline |
|---|---|---|
| Contract (Judge / Target / Stop line / Scope / Runs) | Approval locks a brief; the judge sits OUTSIDE the model (test suite, holdout, real device) | The per-item acceptance check the loop needs |
| Honest miss | A miss with smallest real attempt + measured gap + blocker is a full result | Termination without false-done |
| Never change the judge | Tests/data/target untouchable; special-casing forbidden | Anti test-tampering rule |
| `receipts.py` | Every command claimed in REPORT.md must appear as a Bash tool_use in the stream-json transcript | Catches hallucinated verification |
| `run-all.sh` | Headless runner: `claude -p --output-format stream-json --permission-mode acceptEdits --max-budget-usd 5 --allowedTools ... --append-system-prompt ... --setting-sources project,local` / `--bare`, fresh git repo per run, grader script per case | A working template for launching judged headless sessions |
| Auto-mode detection | Model treats `auto` / `bypassPermissions` as pre-approval of the literal scope; bigger steps go to "Next rung" | How an unattended session self-authorizes safely |
| High mode | Cynefin classify, mental-model deck (`deal.py`), 3 approaches scored vs judge, Meadows leverage ladder, second-order check | Candidate "plan review" rubric |
| Blind LLM judge (`evals/judge/`) | Shuffled A/B/C packets, arm names redacted, scores 0-10 on ambition/grounding/honesty/scope/usefulness | How to evaluate pipeline variants, not individual runs |

## Seed hypotheses (confirm / refute / refine)

- H1 Loop half is solved: Ralph loop (fresh `claude -p` per iteration, plan/prompt file as memory, completion promise + max iterations; official `ralph-wiggum` plugin uses a Stop hook + `.claude/ralph-loop.local.md`). What is NOT solved is termination honesty (premature DONE, gamed completion check).
- H2 Anthropic's harness recipe (initializer agent -> `feature_list.json` with pass booleans + `claude-progress.txt` + `init.sh`; coding agent does ONE feature per session, tests end-to-end, commits) is the canonical plan-as-artifact. Plan "review" there is implicit via tests, not a reviewer agent.
- H3 The plan->review->prompt front half is covered by spec-driven tools (GitHub spec-kit, BMAD, obra/superpowers, Claude Code plan mode + plan-reviewer agents). They mostly use an LLM to grade the plan = the self-grading ambition-skill forbids. Missing piece: an external judge per plan item + a stop line.
- H4 The control knobs that matter headless: `claude -p` flags (`--output-format stream-json`, `--max-turns`, `--max-budget-usd`, `--resume`/`--continue`, `--append-system-prompt`, `--allowedTools`, `--permission-mode`, `--bare`), hooks (Stop, SubagentStop, PreToolUse), Agent SDK `query()` with resume + structured output, Workflow tool, `/loop`, routines, claude-code-action.
- H5 Practitioner consensus on failure modes: context rot (fresh context per iteration wins), test tampering, false-done, scope drift, cost blowups, non-terminating loops. Guardrails: receipts vs transcript, commit per iteration, external graders, iteration + budget caps, read-only verify agents.
- H6 Alternative framing: the loop should be an orchestrator state machine (plan -> per item: prompt -> implement -> judge -> review diff vs contract -> mark pass) rather than a bash while-loop; the review that matters is of the DIFF against the contract, not of the plan.

## Source stack (ranked)

1. Elite forums: EN = Hacker News, Lobste.rs, r/ClaudeAI, r/ClaudeCode; ZH = V2EX, linux.do, cnblogs.com, SegmentFault, NodeSeek; ZH-TW = ithelp.ithome.com.tw, PTT Soft_Job, Dcard 軟體工程師, Medium (繁中)
2. Primary/official: code.claude.com/docs, anthropic.com/engineering, github.com/anthropics/claude-code (plugins/, hooks docs), Agent SDK docs, ghuntley.com (Ralph origin)
3. GitHub via `gh search repos|code|issues` — repos, Stop-hook scripts, orchestrators, and ISSUES (real breakage)
4. Analysis blogs: simonwillison.net, paddo.dev, individual practitioners with numbers
5. Deprioritize: CSDN, Juejin, 51CTO, 简书, mejba.me-style SEO, dev.to listicles, GeeksforGeeks

## Gem criteria

GEM = specific numbers (iterations, cost, pass rates), a real config/script/hook, a named failure with a workaround, or a contradiction with official docs. NOISE = generic praise, listicles, undated, no downsides. Tag every finding.

## Team roster

| Name | Role | Model | Assignment |
|---|---|---|---|
| steer-lead | Steering lead (brain) | opus | REASON / STEER / VERIFY-on-demand / propose EXIT |
| g-loop-en | Gatherer | sonnet | EN: loop mechanics + official primitives (Ralph variants, ralph-wiggum plugin internals, Stop hooks, Agent SDK orchestrators, `claude -p` flags, Anthropic harness post, claude-code-action) |
| g-plan-en | Gatherer | sonnet | EN: plan generation, plan review/critique, per-task prompt synthesis (spec-kit, BMAD, superpowers, plan mode, PRD->task JSON, reviewer/critic agents) |
| g-zh | Gatherer | sonnet | ZH: 中文社区 practice — Claude Code 自动化流水线 / Ralph 循环 / 无人值守 / 规划-审查-执行 |
| verifier | Verifier | sonnet | Idle until handed a load-bearing claim |
| (supervisor) | main session | opus | approve pivots, GOAL-CHECK, final synthesis |

Wave 2 (steer-lead reassigns when a thread saturates): g-loop-en -> EN failure modes & guardrails from forums; g-zh -> ZH-TW community.

## Report paths

- g-loop-en -> `en-loop-mechanics.md`; wave 2 -> `en-failure-modes.md`
- g-plan-en -> `en-plan-review-prompt.md`
- g-zh -> `zh-community.md`; wave 2 -> `zh-tw-community.md`
- verifier -> `verifier-log.md`
- steer-lead -> `steer-log.md` (hypothesis status + coverage, updated as it reasons)
All under this directory. Every claim carries its source URL inline.
