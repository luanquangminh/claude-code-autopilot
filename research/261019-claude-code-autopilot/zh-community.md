# ZH Community Practice: Claude Code end-to-end autopilot (g-zh)

Scope: 简体中文 community. Retrieval note: WebSearch is US-only and weak on Chinese; linux.do and Zhihu return 403/Cloudflare; V2EX worked via public API (`/api/topics/show.json`, `/api/replies/show.json`) + sov2ex search. Best-signal source = V2EX. cnblogs/Zhihu/SegmentFault Ralph articles are mostly translations/paraphrases of EN (Huntley, YC hackathon $297, Boris Cherny 259 PRs) -> NOISE for practice.

Tags: GEM / MEH / NOISE. Confidence: H/M/L.

## Findings table

| # | Claim | Source URL | Forum / repo | Tag | Conf |
|---|---|---|---|---|---|
| 1 | Consensus "unattended" recipe = assembly line: skill=模具, 无人值守队列=流水线; every generation step followed by a reviewer in an INDEPENDENT context (subAgent / headless cli); SPEC生成→CODE生成→冒烟自测+修复→全量测试 as separate passes; human takes over last. OP's worry: AI does unsaid things / skips said things / skews said things | https://www.v2ex.com/t/1235515 | V2EX | GEM | M |
| 2 | Orbi (self-hosted pipeline): GitHub issue label `ai-ready` → AI codes → separate review round → merge → release. 20 merged PRs on DeepSeek: median 10.61M tokens, ~60 min, 156 model calls, median $0.125/PR, max $0.417, 97.1% cache hit. Context window 131K → 32 of 77 sessions got compacted and lost file reads/test output; fixed by 1M window | https://www.v2ex.com/t/1245983 | V2EX | GEM | M (self-reported, own repo, Python+CI, clear tickets) |
| 3 | Ralph loop runaway: overnight UI-align loop (Playwright screenshot diff Vue-vs-React as judge). Stop hook never ended ("No completion promise set - loop runs infinitely", iteration 1466). ccusage ≈ $268, 423M tokens (almost all cache read; Max plan, ≈5% of 5h quota) | https://www.v2ex.com/t/1199391 | V2EX | GEM | H (ccusage table pasted) |
| 4 | Reviewer-never-satisfied: Claude Code writes, Codex MCP reviews in loop; 8 rounds, 7-8 NEW issues each, ≈$100 CC tokens, no convergence. Cause: reviewer had no explicit standard. Fixes: give review criteria; severity-tier & fix only high; "review the review" (ask author "are these reasonable?"); cap AI review at 1-2 rounds then human; anti-over-engineering definition | https://www.v2ex.com/t/1195006 | V2EX | GEM | H |
| 5 | Same pattern with Gemini Code Assistant reviewing Cursor-SDK PRs: always rates medium+ severity → review fatigue, net efficiency negative; conclusion "remove human, let AI self-improve" (cites OpenAI Harness Engineering / Ralph) | https://www.v2ex.com/t/1217464 | V2EX | MEH | M |
| 6 | Gold Band (diodeme/Gold-Band, 150★, Rust/Tauri, ACP): author says Ralph = "又当运动员又当裁判，缺少交叉验证". Node-graph workflow dev→审查→测试→验收; node result judged by agent-emitted JSON + expression (`$.result == true`) or human click; `attempt` (loop-back) and `round` caps; failed review/test loops back via `continue` session; accept node can be a DIFFERENT vendor harness (e.g. Codex w/ computer-use) | https://www.v2ex.com/t/1216451 ; https://github.com/diodeme/Gold-Band | V2EX + GitHub | GEM | M (judge is still an LLM-emitted bool) |
| 7 | Vigil (jzb1006/claude-vigil): queue of `claude -p` in per-task git worktree; `--resume <session_id>` after 5h quota wall (resume_at = limiter.resets_at+60s) and 3x transient retries (30/60/120s); NEVER auto-merge ("让无人值守 agent 自动 merge 是丢系统信任的捷径") — end state = branch awaiting human; PreToolUse scope hook `--scope-write 'src/auth/**'`; post-run self-summary JSON (decisions/assumptions/skipped/merge-risk/confidence); `--depends-on` DAG | https://www.v2ex.com/t/1214573 ; https://github.com/jzb1006/claude-vigil | V2EX + GitHub | GEM | M |
| 8 | Chorus (Chorus-AIDLC/Chorus): "人类决策左移" — idea→elaboration Q&A→tasks with acceptance criteria held server-side; daemon spawns headless `claude -p` whose prompt is only an idea-uuid, context via MCP; session anchored per idea (`--resume`); adversarial-review inside plugin, agent must log own Q&A so human can audit drift afterwards; interrupt = SIGINT then SIGKILL. Skeptics: "真实业务你不人工干预就是一堆屎"; AI over-engineers | https://www.v2ex.com/t/1223573 ; https://www.v2ex.com/t/1213407 | V2EX | GEM | M |
| 9 | `/goal` 80h run (Codex): ~4B tokens, 180k LOC, 200+ commits; one human nudge. Author: "目标有强验收机制成功率高…跑不出来在预期之中"; long-goal got ~10h when acceptance flow was fully designed. Requirement doc came from "1-2 weeks chatting with AI", no special tool | https://www.v2ex.com/t/1228560 | V2EX | MEH (Codex, not CC) | M |
| 10 | ralph-loop scope limits (practitioner replies): "ralph-loop 长时间写功能肯定不行，中间很多决策它做不了；长时间改 bug 可能，前提验收标准完备…唯一半夜全自动成功=brand 重命名这种脏累重又好验证的活"; "需要 ralph-loop + 每个 task 都是可让 AI 验证的" | https://www.v2ex.com/t/1200449 | V2EX | GEM | M |
| 11 | Claude=architect/plan, Codex=critic (`/plan-review`) iterate "until two agree"; then Codex implements, Claude reviews (`/plan-execute`). ZH default for plan review = cross-vendor LLM pair, stop criterion = agreement | https://www.v2ex.com/t/1198247 ; repo longranger2/claude-gpt-workflow | V2EX + GitHub | MEH | M |
| 12 | claude-code-supervisor (guyskk): Stop hook → second Claude instance reviews, feeds back until it approves. = LLM-grades-LLM at the Stop hook | https://www.v2ex.com/t/1184696 | V2EX | MEH | M |
| 13 | SDK harness reality: "业务逻辑只占30%，70%是 harness 防御代码 (token截断、工具重试、无限循环检测、中间结果持久化)" — from 6-agent one-person company, half a year | https://www.v2ex.com/t/1205192 | V2EX | MEH | L-M (promo account 公众号) |
| 14 | SDD cost: "OpenSpec 用了发现太耗令牌，文档对齐耗费的 token 远多于写代码"; "项目久了 SDD 难维护，小改动也花很久" | https://www.v2ex.com/t/1213407 (reply) ; https://www.v2ex.com/t/1204596 | V2EX | MEH | M |
| 15 | Claude Code `/goal` described by ZH blogger as state machine pursuing→achieved/unmet/budget-limited, evidence-based completion, `-p` mode for CI | https://www.v2ex.com/t/1214285 | V2EX | MEH (feature description) | M |
| 16 | ccteam: expensive model (Claude) plans & accepts, 3 Codex workers implement in parallel, then "仓库治理知识沉淀"; acceptance = "高级模型来做" (LLM). Commenter asks "大需求不怕跑偏吗" – no answer | https://www.v2ex.com/t/1230260 | V2EX | MEH | L |
| 17 | atdo (qianminjian/auto-loop-plan, 0★): skill that runs ANY plan file one phase per turn: execute → "独立验证" done by orchestrator itself (file exists / syntax / diff scope / debug residue / secrets) → LLM audit → ≤3 fix loops → gate integration test → commit; 3-strike alert; state.json resume; free-markdown plans must pass human checkpoint. Design = deterministic checks first, LLM audit second | https://github.com/qianminjian/auto-loop-plan | GitHub | MEH | L (0★, unproven) |
| 18 | Enhanced-Ralph guardrails cited in ZH article: dual exit (promise AND EXIT_SIGNAL), 100 calls/hour limit, circuit breaker "最近5次提交无实质变化→死循环", max-iterations "20-100" | https://www.cnblogs.com/Aleck-USTC/articles/19961674 | 博客园 | NOISE (derived from EN frankbria/ralph-claude-code) | L |
| 19 | Stop hook official cap per ZH doc summary: "连续 8 次阻断后放行" | https://segmentfault.com/a/1190000047829691 | SegmentFault | NOISE (doc paraphrase; verify against official docs) | L |
| 20 | Fake-done mitigation: independent verifier + side-effect check + JSON `{status, evidence, verified_by}` + 3x sampling; claims fake-done rate ~30%→~0, +20% time. Top reply: "完成状态不依照 LLM token 表述，靠查验脚本决定" | https://www.v2ex.com/t/1200728 | V2EX | MEH | L (marketing post, unmeasured) |
| 21 | Mandated-autonomy anecdotes: "全AI，必须用 spec，不审查代码，只体验功能，一天跑 $100 都是小问题"; "每开发每月 1-2k 美元 token 才能解决 99% 业务代码" | https://www.v2ex.com/t/1205270 | V2EX | MEH | L |

## Repo verification (steer-lead asks)
- Gold Band `$.result == true`: it is `success_condition.expression` evaluated over the node's JSON OUTPUT, which the agent emits (UI string: "保存时会校验路径是否存在于 JSON 输出约束中"). So = SELF-REPORT of the node agent, not exit code/test run — unless the node's role/prompt runs tests and reports. Source: cloned repo, `web/scripts/en-strings.json:6268`, `web/tests/workflow-editor-interaction-contract.test.ts`. Human-click is the alternative judge. Mitigation is only structural: separate dev/review/test/accept nodes, possibly different vendor.
- Vigil scope hook: real PreToolUse allowlist for Edit/Write/MultiEdit/NotebookEdit (fnmatch, structured deny fed back to Claude) — `README.md` L456-511. Bash is NOT covered: README says "Bash side-effects (network, writes outside worktree) are not stopped by the sandbox", tasks run with `--permission-mode bypassPermissions`; so Bash `sed -i`/`echo >` can bypass scope. Also has `--budget-tokens/--budget-cost` flags (`vigil add`), i.e. a ZH repo with per-task budget caps. Source: https://github.com/jzb1006/claude-vigil README.zh.md L83.
- See also ZH-TW file for measured exit-code-0 false success: zh-tw-community.md.

## Numbers
- Orbi/DeepSeek: median 10.61M tok, 60 min, 156 calls, $0.125/PR (max $0.417; peak-price median $0.249), 97.1% cache hit; 20 PRs [t/1245983].
- Ralph runaway: iteration 1466, ≈$268, 423M tokens, ≈5% of Max 5h quota (cache read free-ish) [t/1199391].
- Cross-vendor review loop: 8 rounds, ≈$100 CC tokens, never converged [t/1195006].
- /goal Codex: 62h+18h, ≈4B tokens, 180k LOC, 200+ commits [t/1228560].
- Claude Max-plan caveat: `claude -p` quota accounting debated in ZH threads [t/1214778, t/1222322] — relevant for headless cost modelling (unverified; EN side should confirm).
- Per-dev monthly budget claim $1-2k [t/1205270] (L). Daily $100 (L).
- No ZH source gives a clean pass rate over N unattended runs. Longest credible run: 80h Codex /goal; longest credible Claude Code: overnight (~8h) UI loop.

## Failure stories (with workaround adopted)
| Failure | Story | Workaround |
|---|---|---|
| 死循环 / 成本失控 | Stop hook w/o promise ran 1466 iters [t/1199391] | always set max-iterations + promise; cost visible via ccusage |
| 假完成 | agent says done, nothing there [t/1200728]; test/verification summary ≠ real run [t/1245178, cnblogs 28 Sep talk: "完成总结和我们能核对的结果之间有距离"] | check scripts decide, not model text; transcript/side-effect check |
| 评审永不收敛 | 8 rounds new issues [t/1195006]; Gemini always objects [t/1217464] | explicit review standard, severity tiers, cap rounds, review-the-review |
| 上下文腐烂/压缩丢状态 | 131K window → 32/77 sessions compacted, re-reads [t/1245983] | full window; per-task fresh session; split into subagents [t/1235515] |
| 偏离架构 | AI edits account table directly instead of module [t/1245178] | project harness: hooks + knowledge map (talk, 博客园 repost) |
| 过度设计 | AI code unreadable after few tasks [t/1223573 reply] | anti-over-engineering prompt; human final review |
| 额度墙/网络抖动 | 5h window kills queue [t/1214573] | `--resume` at reset time, retries with backoff |
| 篡改测试 | In ZH search, tampering is mentioned only generically (Zhihu questions); NO first-hand V2EX story found. | (unresolved) |

## Divergence from EN practice
- CONVERGES: external verification > model self-claim; fresh session per task; one-task-at-a-time; worktree isolation; max-iterations; commit/branch as artifact; "Ralph works where acceptance is mechanical (rename, bugfix), fails on judgment-heavy feature work."
- DIVERGES (1): Plan review in ZH = cross-VENDOR LLM pair (Claude↔Codex) until "agreement", plus human "decision left-shift" up front (Chorus, grill-me). Rarely an external per-item judge. The ZH community has already seen its failure (non-convergence, over-engineering) and answers with rubric + severity tiering + round cap.
- DIVERGES (2): Never auto-merge; terminal state = reviewable branch (Vigil). EN Ralph typically commits straight to branch.
- DIVERGES (3): Cost framing is cache-hit/Max-plan-quota and cheap domestic models (DeepSeek), not $/run budget flags; I found NO mention of `--max-budget-usd`.
- DIVERGES (4): Orchestrators are GUI/daemon products (Gold Band, Chorus, Vigil, ccteam) with web dashboards and IM (Telegram/飞书/企业微信) notifications and remote intervention — not bash while-loops.
- DIVERGES (5): Heavy cross-harness mixing (Claude plans, Codex codes, Grok explores) as a default, partly driven by account bans / quota.
- Not found in ZH: Anthropic initializer/feature_list.json pattern by name; `receipts`-style transcript verification; stream-json analysis.

## Unresolved
- linux.do (likely best ZH forum) unreachable (Cloudflare 403) — needs Chrome MCP or logged session. Zhihu 403 too.
- No ZH first-hand test-tampering story; no multi-run pass-rate data.
- RESOLVED (per verifier/steer-lead): ZH threads conflict on `claude -p` billing (t/1214778 vs t/1222322). Authoritative: June-15 split paused; since 2026-10-07 Max/Team plans include monthly API credits covering SDK and `claude -p`, subscription limits still apply — https://support.claude.com/en/articles/15036540 and /17154008. Don't cite the ZH threads for this.
- linux.do: 403 / Cloudflare unreachable; recorded as unreachable, not searched via login.
- Orbi's "separate review round" details (judge? rubric?) not read; worth fetching orbi.build if lead wants.
- Gold Band `AUTO`/accept-node: is acceptance judged by test run or LLM? Repo docs read only partially.
- Low-star GitHub repos (atdo, ralph-auto-coding 2★, claude-multi-agent-dev 0★, slotht-code-agent 0★) have no usage evidence.
