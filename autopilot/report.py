"""Plan-vs-actual report in the ambition format, from state.json."""
from __future__ import annotations

from typing import Any

from .plan import Plan


def _first_lines(s: str, n: int = 3) -> str:
    lines = [l for l in (s or "").splitlines() if l.strip()]
    return " / ".join(lines[-n:]) if lines else ""


def render(plan: Plan, state: dict[str, Any]) -> str:
    items = state["items"]
    counts = {k: sum(1 for s in items if s["status"] == k)
              for k in ("green", "missed", "blocked", "regressed", "pending", "running")}
    attempts = sum(len(s["attempts"]) for s in items)
    status = state["status"] + (f" ({state['halt_reason']})" if state.get("halt_reason") else "")
    out = [f"# Autopilot report: {plan.plan_id}", "",
           f"Branch `{state['branch']}` in `{state['worktree']}`, base `{state['base_sha'][:7]}`, "
           f"contract `{state['contract_commit'][:7]}`. Status: **{status}**. Not merged.", "",
           "| Items green | missed | blocked | regressed | pending | attempts | cost charged (reported) | wall |",
           "|---|---|---|---|---|---|---|---|",
           f"| {counts['green']} | {counts['missed']} | {counts['blocked']} | {counts['regressed']} | "
           f"{counts['pending'] + counts['running']} | {attempts} | ${state['total_cost_usd']:.2f} "
           f"(${state.get('total_cost_reported_usd', state['total_cost_usd']):.2f}) | {state.get('wall_s', 0) / 60:.1f} min |", ""]
    unapproved: list[str] = []
    for it in plan.items:
        st = next(s for s in items if s["id"] == it.id)
        atts = st["attempts"]
        last = atts[-1] if atts else None
        v = (last or {}).get("verdict") or {}
        out += [f"## {it.id}: {st['status']}", "", f"Goal: {it.goal}", "",
                "| Item | Planned | Actual |", "|---|---|---|"]
        if last:
            rc = v.get("judge_rc")
            actual = (f"exit {rc}" if rc is not None else "not executed") + f" (attempt {last['n']}"
            actual += ", " + ", ".join(v.get("reasons") or ["pass"]) + ")"
            tail = _first_lines(v.get("judge_output", ""))
            if tail:
                actual += ": " + tail.replace("|", "\\|")
        else:
            actual = "no attempt (" + (st.get("note") or "pending") + ")"
        out.append(f"| Judge | `{it.judge.cmd}`, pass {it.judge.pass_rule} | {actual} |")
        if st["status"] == "green":
            target_actual = "reached"
        elif st.get("miss"):
            target_actual = "missed by: " + (st["miss"].get("gap") or "?").replace("\n", " ")[:200].replace("|", "\\|")
        else:
            target_actual = "not reached"
        out.append(f"| Target | {it.target.value} ({it.target.state}) | {target_actual} |")
        touched = set()
        for a in atts:
            if not a.get("reset"):
                touched.update((a.get("verdict") or {}).get("files_changed") or [])
        for s in it.scope:
            hit = any(f == s or f.startswith(s.rstrip('/') + '/') for f in touched)
            out.append(f"| Scope: `{s}` | approved | {'changed' if hit else 'untouched'} |")
        out.append(f"| Attempts | stop line {it.stop_line} | {len(atts)} |")
        reg = st.get("regression")
        if reg:
            out.append(f"| Regression at final HEAD | still green | {'green' if reg.get('passed') else 'RED (' + reg.get('reason', '') + ')'} "
                       f"`{reg.get('sha', '')[:7]}`, canary {reg.get('canary', 'none')} |")
        if atts:
            out += ["", "| # | start → end | verdict | claimed | cost | turns | subtype |", "|---|---|---|---|---|---|---|"]
            for a in atts:
                av = a["verdict"] or {"passed": False, "reasons": ["not_started"]}
                sess, cl = a["session"], a.get("claim") or {}
                verdict = "PASS" if av["passed"] else "FAIL " + ", ".join(av["reasons"])
                if av.get("canary") == "ok":
                    verdict += " (canary ok)"
                if a.get("reset"):
                    verdict += " (reset)"
                out.append(f"| {a['n']} | {a['start_sha'][:7]} → {a['end_sha'][:7]} | {verdict} | {cl.get('claimed_status', '?')} | "
                           f"${a.get('cost_charged', sess['total_cost_usd']):.3f} | {sess['num_turns']} | {sess['subtype']} |")
                for f in av.get("unapproved") or []:
                    unapproved.append(f"{it.id} attempt {a['n']}: {f}")
        if st.get("miss"):
            m = st["miss"]
            out += ["", f"Miss ({m.get('source', 'model self-report')}, blocker kind `{m.get('blocker_kind', '?')}`):",
                    f"- attempt: {m.get('attempt', '')}".replace("\n", " "),
                    f"- gap: {m.get('gap', '')}".replace("\n", " ")[:800],
                    f"- blocker: {m.get('blocker', '')}".replace("\n", " ")]
        if st.get("note"):
            out.append(f"\nNote: {st['note']}")
        out.append("")
    out += ["## Deviations", ""] + ([f"- {d}" for d in state.get("deviations") or []] or ["none"]) + [""]
    out += ["## Unapproved", ""] + ([f"- {u}" for u in unapproved] or ["none"]) + [""]
    out += ["## Next rung", "", plan.next_rung or "none", ""]
    return "\n".join(out)
