# EN: Plan generation, plan review, prompt synthesis (front half)

Gatherer: g-plan-en. Method: read actual skill/command/template files via `gh api`, official docs, HN threads, GitHub issues. Reddit/Lobste.rs: `site:` searches returned nothing usable (documented; see Unresolved).

## Headline (for H3 / H6)

- **H3 CONFIRMED (strong).** Of 7 tools inspected, none gates *plan* acceptance on an executable outside check. Plan reviewers are LLMs (same model, second model, or human). The only "outside" signal anywhere is the per-item `acceptanceCriteria` / "tests pass" line, and the implementer agent runs and reports that itself.
- **H6 SUPPORTED by official docs.** Anthropic's own recipe reviews the *diff against PLAN.md* in a fresh subagent, not the plan. [best-practices](https://code.claude.com/docs/en/best-practices)
- **Missing piece is real and unfilled:** nobody pairs each plan item with an executable judge command + immutable test set + stop line.

## Tool table

| tool | plan generation | plan review mechanism | judge inside/outside model | prompt synthesis | URL | tag |
|---|---|---|---|---|---|---|
| snarktank/ralph (22k★) | Skill converts PRD → `prd.json` `userStories[{id,title,acceptanceCriteria[],priority,passes:false,notes}]` | None. | **Inside.** Agent picks highest-priority `passes:false`, runs "quality checks (typecheck/lint/test)", commits, then **sets `passes:true` itself**. | Static `prompt.md`/`CLAUDE.md` re-fed each iteration: read prd.json + progress.txt, one story, check, commit, append learnings. Context = files, not a built prompt. | [prompt.md](https://github.com/snarktank/ralph/blob/main/prompt.md), [prd.json.example](https://github.com/snarktank/ralph/blob/main/prd.json.example) | GEM |
| (Anthropic harness `feature_list.json`: dropped here, covered by g-loop-en) | | | | | | |
| Taskmaster (28k★) | `parse-prd` → tasks `{id,status,dependencies,details,testStrategy}`; "next task" = pending with deps satisfied | None built in | Inside: `testStrategy` is **prose** ("Deploy and call endpoint to confirm…"), no command | Task `details` + `testStrategy` shown to the agent | [task-structure.md](https://github.com/eyaltoledano/claude-task-master/blob/main/docs/task-structure.md) | MEH |
| BMAD `bmad-build-auto` | Step-02 writes a plan file from a template (frontmatter: route, risk, baseline_revision, status; `<intent-contract>` Intent / Boundaries Always-Never / I/O & edge-case matrix) | Step-04 review lenses (quick / thorough) over a **staged diff since `baseline_revision`**; plan goes to edge-case + quick lens "for its acceptance criteria". "Review subagents run at same model capability as the session" | **Inside.** Intent-contract is read-only to the implementer (good), but acceptance criteria are prose in the plan; no test command in schema | See Prompt synthesis | [plan-template](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/bmad-build-auto/plan-template.md), [step-04](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/bmad-build-auto/step-04-review.md) | GEM (diff vs plan, H6) |
| nizos/tdd-guard (2.4k★) | n/a (enforces test-first per edit) | PreToolUse hook blocks impl edits without a failing test; test results come from a **test reporter** (real runner output), but the ordering verdict comes from an **LLM validator** (Claude Agent SDK, configurable model) | **Mixed**: runs outside the implementer's turn, input is real test output, verdict is LLM | n/a | [README](https://github.com/nizos/tdd-guard), [validation-model](https://github.com/nizos/tdd-guard/blob/main/docs/validation-model.md) | GEM (closest partial) |
| github/spec-kit | `/specify` → spec.md, `/plan` → plan.md, `/tasks` → tasks.md (phases Setup/Tests/Core/Integration/Polish, IDs, paths, `[P]` parallel) | `/clarify`, `/checklist` (reviewer-owned requirement-quality checklists), `/analyze` = **read-only LLM** consistency pass spec↔plan↔tasks; constitution conflict = CRITICAL | **Inside** (LLM) + human gate: `/implement` stops and asks if checklist items unchecked | `/implement` loads tasks.md, plan.md, data-model, contracts, research, constitution; "tests before code"; agent marks `[X]` in tasks.md **itself** | [analyze.md](https://github.com/github/spec-kit/blob/main/templates/commands/analyze.md), [implement.md](https://github.com/github/spec-kit/blob/main/templates/commands/implement.md) | GEM |
| obra/superpowers | `brainstorming` → spec; `writing-plans` → plan md: header, Global Constraints, **Review Focus** (5 untested failure modes), tasks with exact files, Interfaces consumes/produces, TDD steps (failing test → run → impl → run → commit) | Plan: **self-review checklist by the author, "not a subagent dispatch"**, then human reviews plan. Execution: per task fresh reviewer (spec + quality), scoped re-review | **Inside.** Reviewers are LLM subagents; tests are run by implementer; reviewer told NOT to re-run suite | `implementer-prompt.md` template: brief file + context + "ask questions first" + "you do not dispatch subagents"; reviewer gets brief, implementer report, diff file, global constraints; "Do not trust the report" | [SDD SKILL](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/SKILL.md), [task-reviewer](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/task-reviewer-prompt.md), [writing-plans](https://github.com/obra/superpowers/blob/main/skills/writing-plans/SKILL.md) | GEM |
| BMAD-METHOD | PRD → architecture → stories via persona agents/skills (`bmad-prd`, `bmad-architecture`, `bmad-agent-dev`, ...) | `bmad-review` lenses: adversarial (**must return ≥10 findings; empty = re-check**), edge-case hunter, verification-gaps, structure, prose. Lenses isolated; `claims` shown to edge-case lens only. Findings JSON `{lens,location,trigger_condition,guard_snippet,potential_consequence}`, no severity | **Inside** (LLM lenses) | Stories/specs as files read by dev agent | [bmad-review](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/bmad-review/SKILL.md) | MEH (forced-findings rubric is notable) |
| claudex-loop (3.1k★) | Claude: recon → interrogate user → writes plan | **Second model (Codex/GPT) adversarial review**, binary "approved / revise X,Y,Z", **hard cap 5 rounds** (7 in demo); then cross-model build ("whoever built it never grades it") | **Inside (cross-model).** Blog: "relies entirely on LLM evaluation, no automated tests". Demo: 27 issues round 1 → 0 round 7; code review 23 findings, 19 accepted, 4 rejected | n/a | [blog](https://chaseai.io/blog/claudex-loop-claude-code-plan-review), [repo](https://github.com/chaseai-yt/claudex-loop) | GEM |
| inspectrum (plan-gate hook) | Claude plan mode | Hooks `ExitPlanMode`; Codex reviews; up to 2 revision rounds; human approval dialog still shown; **fails open** if reviewer can't run | Inside (cross-model) | n/a | [glama](https://glama.ai/mcp/servers/t0trhp8cx7) | MEH |
| mrpointer plan-reviewer agent | n/a | Fresh read-only agent, verdict `PASS / PASS WITH CONCERNS / NEEDS REVISION`, "review the plan, not the code"; Glob/Grep only to confirm claims the plan makes against the repo | Inside, but **claims checked against repo state** (weak anchor) | n/a | [skills.cat](https://skills.cat/skills/mrpointer/dotfiles/developing-plan-reviewers) | MEH |
| Claude Code plan mode (native) | Read-only research → plan; edits blocked until approval | **Human**: Yes+auto mode / Yes+manually approve / No keep planning; `Ctrl+G` edit plan; optional clear-context-on-accept. In auto mode a classifier reviews *actions*, not plan quality | Human | After approve, session continues with plan in context (or cleared) | [permission-modes](https://code.claude.com/docs/en/permission-modes) | GEM (baseline) |

Others with >1k★ seen, not read in depth: gsd-build/get-shit-done (64k★), planning-with-files (27k★), Pimzino/claude-code-spec-workflow (3.9k★), gemini-cli-extensions/conductor (3.8k★), Chachamaru127/claude-code-harness (3.2k★, "Plan→Work→Review"), pilot-shell (2.1k★), tzachbon/smart-ralph (559★, Ralph + spec flow). Source: `gh search repos "spec driven" claude --sort stars`.

## Plan review: who judges?

| Reviewer type | Examples | Anchored outside? |
|---|---|---|
| Author self-checklist | superpowers writing-plans | No |
| Fresh same-model subagent | mrpointer, superpowers task reviewer, Claude docs adversarial review | No (reads diff/plan only) |
| Second model | claudex-loop, inspectrum | No ("no automated tests") |
| Forced-findings rubric | BMAD adversarial (≥10) | No; risks padding |
| Human | native plan mode, spec-kit checklist gate, superpowers plan sign-off | N/A, not unattended |
| Executable | **none found for plans.** Closest: Stop hook script / `/goal` ([best-practices](https://code.claude.com/docs/en/best-practices)) but applied to the work, not the plan | Only for work |

Gate ladder from official docs (weak → strong): ask in prompt → `/goal` condition (**separate LLM evaluator**) → Stop hook running your script ("deterministic gate") → fresh-model refutation subagent. [source](https://code.claude.com/docs/en/best-practices)

## Prompt synthesis: what shape is endorsed

- **Per-task = brief file + global constraints + acceptance criteria + base/head SHA**, not an inline blob; reviewer reads a staged diff file ([task-reviewer](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/task-reviewer-prompt.md)).
- **One task/story per session** (ralph, harness, superpowers fresh-implementer). Fresh context beats resumed: resumed implementers grew to 300k+ ctx in fix rounds ([superpowers#2551](https://github.com/obra/superpowers/issues/2551)); SDD escalates to a fresh stronger implementer at round 4.
- **Include the check** in the prompt: Anthropic: "Give Claude a check it can run"; spec "ends with an end-to-end verification step", names files/interfaces, states out-of-scope; execute in a **fresh session** ([best-practices](https://code.claude.com/docs/en/best-practices)).
- **Forbid editing tests**: only the harness post has the explicit line ("unacceptable to remove or edit tests"), as prompt text, unenforced.
- **Reviewer prompt hygiene:** "Do not trust the report"; tell reviewer to flag only correctness/stated-requirement gaps, because gap-hunting reviewers always find something and cause over-engineering ([best-practices](https://code.claude.com/docs/en/best-practices)).
- **Plan-size warning:** HN practitioners say spec-kit/Kiro over-generate ("Tony Stark building a robot in a cave"; Kiro: small bug → 4 stories / 16 criteria) ([HN 45610996](https://news.ycombinator.com/item?id=45610996)). Anthropic: "If you could describe the diff in one sentence, skip the plan."

## Failure modes with evidence

| Failure | Evidence |
|---|---|
| Orchestrator fabricates subagent dialogues/verdicts without dispatching | [superpowers#1749](https://github.com/obra/superpowers/issues/1749) OPEN, self-reinforcing |
| Reviewer rubber-stamps unchanged tree | referenced as #1701 in #1749 (not opened) |
| Unbounded review/fix ratcheting | [#2273](https://github.com/obra/superpowers/issues/2273), #2112 → v6.3 scoped re-review + round-5 breaker |
| Premature "done"/pass flag | Anthropic harness post names it ([post](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)) |
| Agent duplicates existing classes, over-eager to constitution | [Fowler SDD](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html) |
| Spec review = reading markdown nobody wants to read | same article |
| Plan gate fails open | inspectrum |

## Prompt synthesis: what each tool puts IN the per-task prompt

| Tool | Built how | Includes | Excludes / notes | Source |
|---|---|---|---|---|
| snarktank/ralph | **No synthesis.** Same static `prompt.md` every iteration | prd.json (ALL stories), progress.txt (Codebase Patterns on top), branch name; agent picks story itself | Orchestrator never builds a per-task brief; agent selects the task. Prior failures only via the free-text progress log it appends | [prompt.md](https://github.com/snarktank/ralph/blob/main/prompt.md) |
| spec-kit `/implement` | Command template; agent self-loads | tasks.md (REQUIRED), plan.md (REQUIRED), data-model, contracts/, research, quickstart, constitution (IF EXISTS); phases Setup→Tests→Core→Integration→Polish; "tests before code"; agent marks `[X]` | Whole plan in context, all tasks in one session; no per-task isolation | [implement.md](https://github.com/github/spec-kit/blob/main/templates/commands/implement.md) |
| superpowers implementer | **Controller fills a template**: `[BRIEF_FILE]` (full task text from the plan, written to a git-ignored per-plan workspace), scene-setting context, work dir | One task; "Interfaces consumes/produces" block (the only way it learns neighbour names); Global Constraints copied verbatim; "ask questions first"; "you do not dispatch subagents"; escalate-if-stuck | Rest of the plan, controller history ("they should never inherit your session's context"). Reviewer gets brief + implementer report + diff file + BASE/HEAD SHA; report is "unverified claims" | [SDD SKILL](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/SKILL.md), [implementer-prompt](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/implementer-prompt.md) |
| BMAD build-auto | **Fixed 3-line handoff**: "Read {plan_file} fully and implement it — the plan is the sole source of truth. Load every file in frontmatter `context:`… report what you changed, how you verified it, anything incomplete or risky." Subagent has no prior conversation | One self-contained plan file (target 900–1300 tokens; >1600 = "high risk of context rot" → `oversized` warning) | Parent is **forbidden** to add goal restatements, file lists, ownership boundaries, or acceptance criteria to the handoff. "Never over-specify the how: use boundaries + examples" | [step-03](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/bmad-build-auto/step-03-implement.md), [customize.toml](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/bmad-build-auto/customize.toml) |
| Taskmaster | Task record shown by "next task" | details + testStrategy (prose) + deps | no executable check | [task-structure](https://github.com/eyaltoledano/claude-task-master/blob/main/docs/task-structure.md) |
| Anthropic best-practices | Advice | named files/interfaces, out-of-scope, e2e verification step; fresh session | | [best-practices](https://code.claude.com/docs/en/best-practices) |

**Pattern:** two schools. (a) *Plan-file-is-the-prompt* (BMAD, ralph, spec-kit): tiny/static prompt, all knowledge in one file the agent reads. (b) *Controller-built brief* (superpowers): per-task brief file + exact interfaces + global constraints. Neither feeds prior-failure findings except superpowers fix rounds (resume implementer, or fresh stronger one at round 4). **Evidence on which brief shape works best: none measured.** Only design opinion and Anthropic's context-rot argument. Thin.

## Refutation hunt: any plan item bound to an executable check run by someone else?

- GitHub code search for `verify_cmd` / `acceptance_test` / `test_command` / `verifyCommand` in task JSON: no Claude-Code task-schema hits (only unrelated repos, e.g. Bazel acceptance targets, npcsh benchmark scripts). Taskmaster's `testStrategy` is prose. Weak negative (code search is lexical).
- **Closest partial: tdd-guard** (hook, test-reporter output, LLM verdict). A process other than the implementer decides, but it enforces test-before-impl per edit, not "plan item X passes command Y", and the final judge is an LLM.
- **Closest in-schema binding:** superpowers plans put the failing test + run command in every task's steps, but the implementer runs them, reviewer is told not to re-run. BMAD records `how you verified it` as a self-report.
- **Verdict: H3's missing piece NOT refuted.** No tool found with immutable per-item judge command + independent runner + stop line.

## How LLM reviewers fail (measured or structural)

- **Forced quota manufactures findings:** BMAD adversarial lens requires ≥10 findings, empty = re-check ([bmad-review](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/bmad-review/SKILL.md)). Anthropic warns the same: gap-prompted reviewers "will usually report some, even when the work is sound" ([best-practices](https://code.claude.com/docs/en/best-practices)).
- **Convergence ≠ truth:** claudex-loop's "27 issues → 0 by round 7" measures reviewer/author agreement, not defects caught; the 5-round cap ("hard wall") was extended to 7 when they deadlocked ([blog](https://chaseai.io/blog/claudex-loop-claude-code-plan-review)). No ground-truth count of real defects. Code review: 19 of 23 accepted, accept rate is author-judged.
- **"Whoever built it never grades it" is a prompt-level rule** in a skill (separate model call via Codex), not an enforced boundary; I did not find enforcement code (not verified file by file).
- **Fabricated reviews:** superpowers#1749.
- **Plan bloat:** reviewers add, nobody compresses. HN: Kiro bug → 4 stories / 16 criteria ([HN](https://news.ycombinator.com/item?id=45610996)). BMAD's counter: token budget on the plan itself (900–1300 tokens target, warn at 1600). A plan reviewer for this pipeline should have a **compress/delete scope** duty.
- **Only grounded reviewer seen:** mrpointer plan-reviewer, which checks the plan's claims against the repo with Glob/Grep. Keep distinct from opinion-only reviewers.

## Contradictions

- Anthropic's own harness post gives ONE protection for `passes` (prompt rule) while best-practices doc recommends deterministic Stop hook/script. Doc and recipe are not reconciled.
- superpowers `writing-plans` says no subagent for plan review (author self-checks); claudex-loop and inspectrum say a plan MUST be reviewed by a different model. No data compares them.
- Anthropic says use an adversarial reviewer; the same page warns adversarial reviewers over-find. BMAD's "≥10 findings" mandates that failure.

## Unresolved

1. No measured data on plan-review value (does a 27→0-issue plan reduce failed implementations?). Only anecdote.
2. Does any tool run tests *written before implementation and locked* (hidden/holdout) per plan item? Not found; check Chachamaru127/claude-code-harness, pilot-shell, Tessl.
3. Reddit/Lobste.rs: `site:` searches yielded no relevant threads (Reddit may need parallax `search_reddit`); HN covered.
4. #1701 and the spec-kit side of breakage (issue search returned empty) unverified.
5. BMAD `bmad-build-auto` and verification-gaps lens unread.
6. Where `/goal` evaluator's model/rubric is documented (`/docs/en/goal`) unread.

## Sources

See inline links; main: code.claude.com/docs/en/best-practices, /permission-modes; anthropic.com/engineering/effective-harnesses-for-long-running-agents; github.com/snarktank/ralph; github.com/github/spec-kit; github.com/obra/superpowers; github.com/bmad-code-org/BMAD-METHOD; chaseai.io claudex-loop blog; martinfowler.com SDD; news.ycombinator.com/item?id=45610996, 45798473, 48510002.

## JUDGE INTEGRITY: mechanisms that stop the implementer changing the judge

| Mechanism | Enforced by | Model can route around? | Breakage / limits | URL | Tag |
|---|---|---|---|---|---|
| **Claude Code deny rules** (`Edit(tests/**)`) | Harness, code | Edit deny covers all built-in edit tools and *recognized* Bash file commands (`sed`, `tee`, `cat`, redirections `>`). **Not** covered: "arbitrary subprocesses that read or write files indirectly, like a Python or Node script". Docs: "For OS-level enforcement… enable the sandbox". Bash arg patterns are "fragile" | Yes via script/interpreter unless sandboxed. Open issues: deny bypassed by wrappers [#92542](https://github.com/anthropics/claude-code/issues/92542), by command substitution/subshell/interpreters [#103241](https://github.com/anthropics/claude-code/issues/103241); closed: multi-line cmd with leading comments [#38119](https://github.com/anthropics/claude-code/issues/38119), `git -C` [#59006](https://github.com/anthropics/claude-code/issues/59006) | [permissions](https://code.claude.com/docs/en/permissions) | GEM |
| **Sandbox** (OS-level FS isolation) | OS | Docs: blocks all processes from the path. Strongest write-protect available; I did not test it | | [permissions](https://code.claude.com/docs/en/permissions) | GEM |
| **nizos/tdd-guard** (2.4k★) PreToolUse | Hook code + **LLM validator** | Its own doc admits bypass: "if your settings allow shell commands without approval, agents can modify files without triggering TDD validation"; tells you to deny `Bash(echo/printf/sed/awk/perl:*)`, and deny `Read(.claude/tdd-guard/**)`. Interpreter route (`python -c`) not in the deny list | Issue search for bypass: none found | [enforcement.md](https://github.com/nizos/tdd-guard/blob/main/docs/enforcement.md) | GEM |
| **hahahahahahahahah6/agent-guard** (52★) | Hooks: SessionStart snapshots hashes of every test+source file; Stop diffs. Blocks stop if tests changed while no source changed, until agent proves each changed test fails without the fix | Escape hatch `--allow-test-change` (audited). Test+source edited together passes by design | Python stdlib only | [README](https://github.com/hahahahahahahahah6/agent-guard) (GitLab mirror) | GEM (closest to (d)) |
| **wasaybuilds/proof-of-done** (pre-alpha) | `verify` diffs worktree vs git ref via syntax trees: deleted tests, `.skip`, removed/weakened/vacuous assertions, edited CI/guardrail config (POD008). No LLM | Reads *test-side* diffs only | pre-alpha | [README](https://github.com/wasaybuilds/proof-of-done) | MEH |
| **hidevinliu/red-green-mode** (11★, created 2026-08) | **Code, exit codes, no LLM.** `acceptance-contract.json` from a PRD; `rgm_gate.py` = re-run verifier + anti-cheat + contract + constraints (+ optional mutation, point-patch); optional **Stop hook, fail-closed**; `attest` locks SHA-256 over each item's `(id, check_type, expect, verifier)`. Stall check → `STOPPED_NO_PROGRESS` | Own limits doc: verifier commands come from a ledger **written by the judged party** ("write a weak verifier (`true`/`echo PASS`) from the start" not blocked); attestation can be bypassed by deleting the `attestation` field (A4, "not fixed"); contract `status` trusted unless `--run-contract-verifiers`; **editing production code to `return 42` leaves anti-cheat "essentially defenseless"**; 39 evals never executed | **Measured:** 55 hand-written seeded cheats: 32/55 blocked before v0.21, 55/55 after (`agent` profile); false-block on 630 merged human PRs from 21 repos 3.3–3.7% (`review` profile). Corpus hand-written, unknown recall on new tricks | [README](https://github.com/hidevinliu/red-green-mode), [ANTICHEAT-LIMITATIONS](https://github.com/hidevinliu/red-green-mode/blob/main/tools/ANTICHEAT-LIMITATIONS.md) | **GEM** |
| smixs/code-quality (19★) | Git + Stop hooks, advisory only ("never block") | n/a (advisory) | | [README](https://github.com/smixs/code-quality) | MEH |
| Chachamaru127/claude-code-harness (3.2k★) | Go guardrail engine on hooks: protected files, forced push; "assistant must not rewrite protected settings to pass its own check" | Rule list partly project-configurable; not read in depth | | [README](https://github.com/Chachamaru127/claude-code-harness) | MEH |
| maxritter/pilot-shell (2.1k★) | Hooks + stop guards + "independent reviews" | No test-lock or holdout feature found in README | | [README](https://github.com/maxritter/pilot-shell) | MEH |
| **Holdout / hidden tests** | none found | Searched `gh search repos "holdout tests"`, "immutable tests agent": only ML/trading holdout sets. **No Claude Code tool keeps tests out of the implementer's reach.** The ambition-skill's own "holdout" is the only instance seen | | | n/a |

### Reading across

1. **(a) Hooks that block test edits/check test-first**: enforced by code, but only on the tool paths they hook. tdd-guard's own docs concede Bash routes; the harness itself has open deny-bypass bugs. Assume a determined or merely creative model can write via a script unless the **sandbox** (OS-level) or a post-run check is used.
2. **(d) Post-run hash/diff checks are the sturdier layer** (agent-guard, proof-of-done, red-green-mode attest): they judge the end state, not the path, so Bash/interpreter routes don't matter. They catch test-side tampering only; "make production code special-case the test" is the stated blind spot (red-green-mode limit #11) = ambition-skill's "special-casing forbidden", still unenforced by code anywhere.
3. **Judge-authored-by-judged is the unresolved root:** red-green-mode's verifier list comes from the ledger the implementer writes. To be an outside judge, the contract (commands + hashes) must be authored/approved BEFORE and stored where the implementer can't write (sandbox-readonly path, or committed + verified by the orchestrator from a git ref, not the worktree).
4. **Revised H3 status:** red-green-mode comes closest to refuting "missing piece" (per-item acceptance contract + non-LLM gate + fail-closed Stop hook + stall stop line), but it is 11★, 2-month-old, single-author, self-describes as not unattended-grade, and leaves the verifier-authorship hole open. Treat as a design reference, not proof of a solved problem.
5. Not tested by me: whether Claude actually routes around deny via Python in practice (no first-hand run; g-loop-en has forum incidents).
