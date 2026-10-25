"""The state machine: one worktree per run, one fresh session per attempt, code decides everything."""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

from . import gitx
from .judge import HARD_RESET_REASONS, judge_attempt, judge_state
from .lock import LockInfo
from .plan import Item, Plan
from .prompt import REPORT_SCHEMA, SYSTEM_RULES, build_brief
from .runner import SessionConfig, run_session

STATE_FILE = "state.json"
LOCK_FILE = "run.lock"
STOP_FILE = "STOP"
TERMINAL = ("green", "missed", "blocked", "regressed")


class RunLocked(RuntimeError):
    pass


@dataclass
class RunConfig:
    run_dir: Path
    claude_cmd: list[str] = field(default_factory=lambda: ["claude"])
    model: str | None = None
    max_turns: int | None = None
    env: dict[str, str] = field(default_factory=dict)
    tmp_root: Path | None = None
    log: Callable[[str], None] = print


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def acquire_lock(run_dir: Path) -> bool:
    """Atomically take run.lock. Returns False when this process already holds it."""
    run_dir.mkdir(parents=True, exist_ok=True)
    lock = run_dir / LOCK_FILE
    for _ in range(2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            try:
                pid = int(lock.read_text().strip() or 0)
            except (ValueError, FileNotFoundError):
                pid = 0
            if pid == os.getpid():
                return False
            if pid and _pid_alive(pid):
                raise RunLocked(f"another run holds {lock} (pid {pid})")
            lock.unlink(missing_ok=True)          # stale: owner is dead
            continue
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    raise RunLocked(f"could not take {lock}")


def release_lock(run_dir: Path) -> None:
    (Path(run_dir) / LOCK_FILE).unlink(missing_ok=True)


@contextmanager
def run_lock(run_dir: Path) -> Iterator[None]:
    owned = acquire_lock(Path(run_dir))
    try:
        yield
    finally:
        if owned:
            release_lock(Path(run_dir))


class Run:
    def __init__(self, plan: Plan, lock_info: LockInfo, repo: str | Path, cfg: RunConfig) -> None:
        self.plan, self.lock_info, self.repo, self.cfg = plan, lock_info, Path(repo), cfg
        self.run_dir = Path(cfg.run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.branch = f"autopilot/{plan.plan_id}"
        self.worktree = self.run_dir / "worktree"
        self.state: dict[str, Any] = self._load_state()
        self.t0 = time.time()

    # ---- state -------------------------------------------------------------------------
    def _load_state(self) -> dict[str, Any]:
        p = self.run_dir / STATE_FILE
        if p.exists():
            st = json.loads(p.read_text())
            if st.get("plan_id") == self.plan.plan_id and st.get("contract_commit") == self.lock_info.contract_commit:
                return st
        return {"plan_id": self.plan.plan_id, "branch": self.branch, "worktree": str(self.worktree),
                "base_sha": self.plan.base_sha, "contract_commit": self.lock_info.contract_commit,
                "status": "pending", "halt_reason": "", "started_at": 0.0, "finished_at": 0.0,
                "wall_s": 0.0, "total_cost_usd": 0.0, "total_cost_reported_usd": 0.0, "deviations": [],
                "items": [{"id": it.id, "status": "pending", "attempts": [], "miss": None, "note": ""}
                          for it in self.plan.items]}

    def save(self) -> None:
        (self.run_dir / STATE_FILE).write_text(json.dumps(self.state, indent=2) + "\n")

    def item_state(self, item_id: str) -> dict[str, Any]:
        for st in self.state["items"]:
            if st["id"] == item_id:
                return st
        raise KeyError(item_id)

    def deviation(self, text: str) -> None:
        self.cfg.log("deviation: " + text)
        self.state["deviations"].append(text)

    def elapsed(self) -> float:
        return self.state["wall_s"] + (time.time() - self.t0)

    # ---- guards ------------------------------------------------------------------------
    def halt_reason(self) -> str | None:
        g = self.plan.glob
        if (self.run_dir / STOP_FILE).exists():
            return "STOP file present"
        if self.state["total_cost_usd"] >= g.max_cost_usd:
            return f"cost cap reached (${self.state['total_cost_usd']:.2f} >= ${g.max_cost_usd})"
        if self.elapsed() >= g.max_wall_minutes * 60:
            return f"wall clock cap reached ({g.max_wall_minutes} min)"
        if sum(len(s["attempts"]) for s in self.state["items"]) >= g.max_attempts_total:
            return f"attempt cap reached ({g.max_attempts_total})"
        return None

    # ---- worktree ----------------------------------------------------------------------
    def ensure_worktree(self) -> Path:
        if (self.worktree / ".git").exists():
            return self.worktree
        porcelain = gitx.out(self.repo, "worktree", "list", "--porcelain", check=False)
        if f"branch refs/heads/{self.branch}\n" in porcelain + "\n":
            where = [l for l in porcelain.splitlines() if l.startswith("worktree ")]
            raise RuntimeError(f"branch {self.branch} is already checked out in another worktree "
                               f"({'; '.join(where)}); reuse that run dir or pick another plan_id")
        if gitx.branch_exists(self.repo, self.branch):
            gitx.worktree_add(self.repo, self.worktree, "", branch=self.branch)
        else:
            gitx.worktree_add(self.repo, self.worktree, self.plan.base_sha, new_branch=self.branch)
        return self.worktree

    def restore_branch(self, wt: Path, rev: str) -> None:
        """Force the run branch back to `rev`, re-attach HEAD, drop uncommitted leftovers."""
        gitx.git(wt, "checkout", "-q", "-B", self.branch, rev)
        gitx.reset_hard(wt, rev)

    def session_config(self) -> SessionConfig:
        g = self.plan.glob
        return SessionConfig(claude_cmd=list(self.cfg.claude_cmd), model=self.cfg.model or g.model,
                             max_turns=self.cfg.max_turns, max_budget_usd=g.max_budget_usd_per_attempt,
                             timeout_s=g.attempt_timeout_s, allowed_tools=list(g.allowed_tools),
                             env=dict(self.cfg.env))

    # ---- main loop ---------------------------------------------------------------------
    def run(self) -> dict[str, Any]:
        owned = acquire_lock(self.run_dir)
        try:
            return self._run()
        except Exception as e:                       # never leave state at "running"
            self._halt(f"error: {type(e).__name__}: {e}")
            raise
        finally:
            if owned:
                release_lock(self.run_dir)

    def _run(self) -> dict[str, Any]:
        st = self.state
        if not st["started_at"]:
            st["started_at"] = time.time()
        st["status"] = "running"
        st["halt_reason"] = ""
        self.save()
        wt = self.ensure_worktree()
        self.cfg.log(f"run {self.plan.plan_id}: branch {self.branch} in {wt}")
        for item in self.plan.items:
            ist = self.item_state(item.id)
            if ist["status"] in TERMINAL:
                continue
            halt = self.halt_reason()
            if halt:
                return self._halt(halt)
            if not self._run_item(item, ist, wt):
                return self._halt(st["halt_reason"])
        self._regression_pass(wt)
        st["status"] = "done"
        st["finished_at"] = time.time()
        st["wall_s"] = self.elapsed()
        self.save()
        return st

    def _halt(self, reason: str) -> dict[str, Any]:
        st = self.state
        st["status"], st["halt_reason"] = "halted", reason
        st["finished_at"] = time.time()
        st["wall_s"] = self.elapsed()
        self.cfg.log("halted: " + reason)
        self.save()
        return st

    def _regression_pass(self, wt: Path) -> None:
        """Every green item must still pass on the final HEAD; later items can break earlier ones."""
        final = gitx.head(wt)
        for item in self.plan.items:
            ist = self.item_state(item.id)
            if ist["status"] != "green":
                continue
            out = judge_state(item, self.lock_info, wt, final, self.cfg.tmp_root)
            ist["regression"] = {"sha": final, **out.to_dict()}
            if not out.passed:
                ist["status"] = "regressed"
                ist["note"] = f"green after its own attempts, red at final HEAD {gitx.short(final)} ({out.reason})"
                self.deviation(f"{item.id}: regressed at final HEAD ({out.reason})")
        self.save()

    def _run_item(self, item: Item, ist: dict[str, Any], wt: Path) -> bool:
        """False means the run must halt (reason already in state)."""
        log = self.cfg.log
        g = self.plan.glob
        ist["status"] = "running"
        if gitx.is_dirty(wt):
            gitx.reset_hard(wt, gitx.head(wt))
            self.deviation(f"{item.id}: discarded uncommitted changes left in the worktree before the item")
        pre = judge_state(item, self.lock_info, wt, gitx.head(wt), self.cfg.tmp_root)
        if pre.passed:
            ist["status"] = "green"
            ist["note"] = "judge already green before any attempt; no session run"
            self.deviation(f"{item.id}: judge was already green at {gitx.short(gitx.head(wt))}; item skipped")
            self.save()
            return True
        while True:
            halt = self.halt_reason()
            if halt:
                self.state["halt_reason"] = halt
                self.save()
                return False
            if len(ist["attempts"]) >= item.stop_line:
                break
            n = len(ist["attempts"]) + 1
            start = gitx.head(wt)
            log(f"{item.id}: attempt {n}/{item.stop_line} from {gitx.short(start)}")
            brief = build_brief(self.plan, item, ist["attempts"])
            sess = run_session(self.session_config(), brief, cwd=wt,
                               out_dir=self.run_dir / "attempts" / f"{item.id}-{n}",
                               schema=REPORT_SCHEMA, system_prompt=SYSTEM_RULES, name="implement")
            charged = sess.total_cost_usd if sess.has_result else g.max_budget_usd_per_attempt
            self.state["total_cost_usd"] += charged
            self.state["total_cost_reported_usd"] += sess.total_cost_usd
            if not sess.started:
                att = {"n": n, "start_sha": start, "end_sha": start, "progress": False, "reset": False,
                       "cost_charged": charged, "session": sess.to_dict(), "verdict": None, "claim": {}}
                ist["attempts"].append(att)
                self.state["halt_reason"] = (f"claude produced no output (exit {sess.exit_code}); check the command, "
                                             f"flags and model: {sess.stderr_tail[-300:]!r}")
                self.save()
                return False
            verdict = judge_attempt(self.plan, item, self.lock_info, wt, start, sess, self.branch,
                                    self.cfg.tmp_root, log)
            claim = sess.structured_output or {}
            end = verdict.end_sha or gitx.head(wt)
            reset = any(r in HARD_RESET_REASONS for r in verdict.reasons)
            progress = (not reset) and gitx.tree_of(wt, start) != gitx.tree_of(wt, end)
            att = {"n": n, "start_sha": start, "end_sha": end, "progress": progress, "reset": reset,
                   "cost_charged": charged, "session": sess.to_dict(), "verdict": verdict.to_dict(), "claim": claim}
            ist["attempts"].append(att)
            log(f"{item.id}: attempt {n} -> {'PASS' if verdict.passed else 'FAIL ' + ', '.join(verdict.reasons)}"
                f" (claimed {claim.get('claimed_status', '?')}, ${sess.total_cost_usd:.3f}, {sess.subtype}, canary {verdict.canary})")
            if verdict.fake_receipts:
                self.deviation(f"{item.id} attempt {n}: claimed commands never run: " + "; ".join(verdict.fake_receipts))
            if verdict.unapproved:
                self.deviation(f"{item.id} attempt {n}: files outside scope: " + ", ".join(verdict.unapproved))
            if verdict.suspicious:
                self.deviation(f"{item.id} attempt {n}: suspicious additions: " + "; ".join(verdict.suspicious))
            self.save()
            if verdict.passed:
                ist["status"] = "green"
                break
            if any(r.startswith("contract_ref_tampered") for r in verdict.reasons):
                self.state["halt_reason"] = "contract ref tampered; refusing to continue"
                self.save()
                return False
            if reset:
                self.restore_branch(wt, start)
                self.deviation(f"{item.id} attempt {n}: branch restored to {gitx.short(start)} ({', '.join(verdict.reasons)})")
            miss = claim.get("miss") if isinstance(claim.get("miss"), dict) else None
            if miss and miss.get("blocker_kind") == "judge_contradicts_spec":
                ist["status"] = "blocked"
                ist["miss"] = miss
                ist["note"] = "model claims the judge contradicts the spec; unverified; a human decides"
                break
            streak = 0
            for a in reversed(ist["attempts"]):
                if a["progress"]:
                    break
                streak += 1
            if streak >= g.no_progress_limit:
                ist["note"] = f"stopped early: {streak} attempts without progress"
                break
        if ist["status"] == "running":
            ist["status"] = "missed"
            ist["miss"] = self._synth_miss(ist)
        self.save()
        return True

    @staticmethod
    def _synth_miss(ist: dict[str, Any]) -> dict[str, Any]:
        last = ist["attempts"][-1] if ist["attempts"] else {}
        claim = last.get("claim") or {}
        miss = claim.get("miss") if isinstance(claim.get("miss"), dict) else {}
        if claim.get("claimed_status") == "miss" and any(miss.get(k) for k in ("attempt", "gap", "blocker")):
            return {**miss, "source": "model self-report"}
        v = last.get("verdict") or {}
        return {"attempt": f"{len(ist['attempts'])} attempt(s); last changed: " + (", ".join(v.get("files_changed") or []) or "nothing"),
                "gap": (v.get("judge_output") or "")[-600:] or ", ".join(v.get("reasons") or []),
                "blocker": "not reported by the model", "blocker_kind": "other", "source": "orchestrator"}
