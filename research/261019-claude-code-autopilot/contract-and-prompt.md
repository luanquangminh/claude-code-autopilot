# Plan Contract and Per-Item Prompt

Concrete shapes for stages 1 to 6 of [architecture.md](architecture.md). JSON over Markdown: the harness post chose JSON because the model is less likely to edit it inappropriately. The example item is illustrative, not taken from any real repo.

## plan.json

```json
{
  "plan_id": "261020-refund",
  "base_sha": "8be3766",
  "contract_ref": "refs/contract/261020-refund",
  "global": { "max_cost_usd": 20, "max_wall_minutes": 180, "max_attempts_total": 30, "no_progress_limit": 3 },
  "items": [
    {
      "id": "refund-endpoint",
      "goal": "POST /refund returns 200 and records a refund row",
      "scope": ["src/payment/refund.py", "src/payment/routes.py"],
      "judge": { "cmd": "python3 -m pytest tests/test_refund.py -q", "pass": "exit 0",
                 "paths": ["tests/test_refund.py"], "sha256": "..." },
      "target": { "value": "4/4 tests", "state": "proven (tests/test_refund.py)" },
      "stop_line": 3,
      "status": "pending", "attempts": [], "miss": null
    }
  ]
}
```

Lint rules before lock: `judge.cmd` runs and FAILS on `base_sha`; every `judge.paths` entry exists; `scope` and `judge.paths` do not overlap; `stop_line >= 1`; `target.state` is proven, unreasonable on purpose, or guess.

## Per-item prompt (controller-built brief, fresh session)

```
You are implementing ONE item of an approved plan. The contract is locked.

ITEM refund-endpoint: POST /refund returns 200 and records a refund row.
SCOPE (only these files may change): src/payment/refund.py, src/payment/routes.py
JUDGE (do not change this check, its files, or its data):
  python3 -m pytest tests/test_refund.py -q   -> pass = exit 0
TARGET: 4/4 tests (proven: tests/test_refund.py)
INTERFACES: consumes PaymentRepo.insert(dict); produces RefundResult(id, status)
GLOBAL CONSTRAINTS: <verbatim from the plan>
PRIOR ATTEMPT 1 judge output:
  <pasted tail of judge stdout and stderr>

Work in this worktree. Run the judge yourself before you stop. Commit on green with
the message "refund-endpoint: <what>". If you cannot reach the target, stop and report
the miss with the real judge output: smallest real attempt, measured gap, blocker. That
is a good result. Do not special-case the judge in production code. Do not edit anything
outside SCOPE. Finish by filling the JSON schema you were given.
```

Shape follows superpowers' brief (one task, interfaces, constraints verbatim), BMAD's size budget (plan slice about 900 to 1300 tokens, warn at 1600), Anthropic's "give Claude a check it can run", and ambition's honest-miss line. No source measures brief shape; this is design, not data.

## Structured self-report (`--json-schema`)

```json
{ "type": "object", "required": ["claimed_status", "commands_run", "files_changed", "miss"],
  "properties": {
    "claimed_status": { "enum": ["green", "miss"] },
    "commands_run":   { "type": "array", "items": { "type": "string" } },
    "files_changed":  { "type": "array", "items": { "type": "string" } },
    "miss": { "type": ["object", "null"],
              "properties": { "attempt": {"type":"string"}, "gap": {"type":"string"}, "blocker": {"type":"string"} } }
  } }
```

The orchestrator treats every field as a claim. `commands_run` is checked by `receipts.py` against the transcript, `files_changed` against `git diff --name-only`, and `claimed_status` is ignored for the verdict.

## Invocation

```bash
claude -p "$(cat brief.txt)" \
  --model claude-sonnet-5-5 --output-format stream-json --verbose \
  --json-schema "$(cat report.schema.json)" \
  --permission-mode acceptEdits --permission-prompts none \
  --allowedTools Read Edit Write Glob Grep "Bash(python3:*)" "Bash(git add:*)" \
    "Bash(git commit:*)" "Bash(git diff:*)" "Bash(git status:*)" \
  --max-turns 60 --max-budget-usd 2 --no-session-persistence \
  --setting-sources project,local \
  --append-system-prompt-file contract-system.txt \
  > transcript.jsonl 2> stderr.txt
```

Notes from the docs: `stream-json` needs `--verbose`. `--max-budget-usd` can overshoot by one response plus running subagents and resets per `--resume`, so sum `total_cost_usd` yourself. `--bare` is recommended and will become the `-p` default but needs `ANTHROPIC_API_KEY`, so subscription logins keep `--setting-sources`. `--json-schema` output lands in `structured_output` of the final `result` message. An unset permission mode may resolve to `auto`, so always pass one. Project hooks and `.mcp.json` servers run under `-p` unless `--bare`. Pin `--model`: an unpinned scheduled job silently ran the most expensive default (iThome).

## Related

[architecture.md](architecture.md) · [judge-integrity.md](judge-integrity.md) · [loop-primitives.md](loop-primitives.md)
