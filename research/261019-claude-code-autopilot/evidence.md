# Evidence: Numbers, Contradictions, Unresolved

## Measured numbers

| Number | What | Source | Confidence |
|---|---|---|---|
| 1,466 iterations, about $268, 423M tokens | Overnight Ralph Stop-hook loop with a real Playwright judge but no promise and no cap | [v2ex 1199391](https://www.v2ex.com/t/1199391) | high (ccusage pasted) |
| 32 of 77 sessions compacted at 131K | Lost file reads and test output; fixed by a 1M window | [v2ex 1245983](https://www.v2ex.com/t/1245983) | medium (self-reported) |
| $0.125 median per merged PR, 20 PRs, about 60 min, 156 calls, 97% cache hit | Issue label, then AI, then review, then merge, on DeepSeek | same | medium |
| 8 rounds, about $100, no convergence | Claude writes, Codex reviews, no criteria | [v2ex 1195006](https://www.v2ex.com/t/1195006) | high |
| 80 h, about 4B tokens, 200+ commits, 1 nudge | `/goal` run on Codex; success "tracks the strength of the acceptance check" | [v2ex 1228560](https://www.v2ex.com/t/1228560) | medium |
| 4 of 4 do-nothing runs exit 0 plus "success"; 13 of 13 scheduler runs logged success including blocked ones | `claude -p` false success, server-side logs | [iThome Day 28](https://ithelp.ithome.com.tw/articles/10423514) | high; verifier reproduced locally (exit 0, `subtype: success`, file not created) |
| 51,673 tokens, $0.335 | `claude -p` cold start on an empty folder | [iThome Day 1](https://ithelp.ithome.com.tw/articles/10403459) | medium |
| 2, then 4, then 12 tickets | Overlapping runs, then a non-overlapping scheduler, both duplicated | iThome Day 28 | high |
| 123 of 131 on-call tickets were duplicates | Another auto-system, Jun to Sep | iThome Day 28 | medium |
| 0.7% / 30.4% / 100% | o3 reward-hack rate on HCAST / RE-Bench / one task | [METR](https://metr.org/blog/2025-06-05-recent-reward-hacking) | high, confounded |
| 55 of 55 at 12.7% false blocks | red-green-mode agent profile; recall reproduced by the verifier | [repo](https://github.com/hidevinliu/red-green-mode) | medium |
| hundreds of rounds; about 15 re-fires | `/goal` loops on user-only auth; after a permission denial | #100010, #98066 | high |
| 8 consecutive blocks | Stop-hook cap, resets on any tool call | [hooks docs](https://code.claude.com/docs/en/hooks) | verified |
| $100 / $200 monthly API credits | Max 5x / 20x, cover `claude -p` and the SDK since 2026-10-07; the June split was paused | [support](https://support.claude.com/en/articles/17154008-monthly-api-credits-for-max-and-team-plans) | verified |
| 300k+ tokens | Resumed implementer context in fix rounds | superpowers #2551 | medium |
| 39 of 39 correct; $0.013 and 7 s vs $0 and 0.1 s | LLM checker vs a 50-line stdlib evidence gate on the same cases | [iThome Day 19](https://ithelp.ithome.com.tw/articles/10420353) | medium (n=39, one author) |
| about 3 weeks | A daily scheduled `claude -p` check failed silently (empty prompt from an encoding bug) | iThome Day 28 | medium |

Series note: Days 19, 20 and 28 are from 「買了 Claude Code，然後呢？」; only the cold-start figure is from 「我讓 Claude Code 自己跑了五個月」.

Unverified, do not cite as data: $858 plus $960 and $6,000 overnight bills, "1,966 attempts" (paywalled or secondhand); "fake-done 30% to 0" (promotional post); Huntley's $297 and "6 repos overnight" (anecdote).

## Contradictions resolved

| Claim A | Claim B | Resolution |
|---|---|---|
| Brief: ralph-wiggum = fresh `claude -p` per iteration | Source: same session, same prompt re-fed | B. Fresh context is Huntley's bash loop, ralphex, continuous-claude |
| Docs: infinite hook loops are prevented | #100010: hundreds of rounds | Both. The 8-block cap resets on every tool call |
| ralphex README: validation commands gate tasks | Go code never runs them | B, refuted at source |
| ralphex README: SDK credit split from June 15 | Anthropic: paused; Oct 7 credits instead | B |
| `/goal` is "decided by a fresh model" | the evaluator runs no tools | Independent model, not independent evidence |
| red-green-mode "55 of 55 with 3.3 to 3.7% false blocks" | the numbers belong to two profiles | 55 of 55 goes with 12.7%; 3.3 to 3.7% goes with a review profile that lets 14 cheats warn |
| hooks reference wording on `stop_hook_active`, as a gatherer quoted it | local test | "already continuing"; no "configured" definition exists on either docs page |

## Unresolved

- No A/B measurement of same-session versus fresh-context loops anywhere.
- No measured effect of plan review on implementation outcomes (claudex's 27 to 0 is agreement, not defects).
- No tool keeps tests out of the implementer's reach (holdout); ambition-skill's `d-depth` holdout is the only instance seen.
- Whether an agent-type Stop hook's `ok: false` shares the 8-block cap.
- Whether `/goal` under `-p` plus a command Stop hook interact safely.
- Which pool a `claude -p` call draws from first under the new Max credits.
- iThome Day 6 (agreed completion conditions, the 88% cold-start cost cut) could not be located within the fetch cap. Day 19 was read; see [judge-integrity.md](judge-integrity.md).
- Reddit, Lobste.rs, linux.do, Zhihu, PTT and Dcard were unreachable in this run.

## Related

[overview.md](overview.md) · [architecture.md](architecture.md) · [judge-integrity.md](judge-integrity.md) · raw reports listed in the overview
