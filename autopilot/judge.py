"""Judge an attempt on the COMMITTED end state, with the judge read from the contract ref.

Order, fail closed at each step: contract ref intact -> HEAD on the run branch -> start is an
ancestor of HEAD -> at least one commit -> judge files untouched -> scope respected -> receipts
-> execute the judge in a clean checkout of HEAD with judge files overlaid from the contract
-> if green, run it again with a canary test that must fail (exit 0 then = broken oracle).
"""
from __future__ import annotations

import fnmatch
import secrets
import shlex
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import gitx
from .lock import LockInfo, verify_ref
from .plan import Item, Plan
from .procs import run_shell
from .receipts import bash_commands, fake_claims
from .runner import SessionResult

HARD_RESET_REASONS = ("judge_tampered", "out_of_scope", "branch_detached", "history_rewritten")
SUSPICIOUS = ("os._exit", "atexit", "unittest", "pytest", "sys.modules", "SystemExit")
UNITTEST_CANARY = ("import unittest\n\n\nclass AutopilotCanary(unittest.TestCase):\n"
                   "    def test_canary(self):\n        self.fail('autopilot canary: this test must fail')\n")
PYTEST_CANARY = "def test_autopilot_canary():\n    assert False, 'autopilot canary: this test must fail'\n"


@dataclass
class JudgeOutcome:
    passed: bool
    rc: int | None
    output: str
    timed_out: bool
    canary: str          # ok | broken | none
    reason: str          # "" | judge_red | judge_timed_out | judge_oracle_broken

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Verdict:
    passed: bool = False
    reasons: list[str] = field(default_factory=list)
    commits: int = 0
    files_changed: list[str] = field(default_factory=list)
    unapproved: list[str] = field(default_factory=list)
    tampered: list[str] = field(default_factory=list)
    fake_receipts: list[str] = field(default_factory=list)
    claim_mismatch: list[str] = field(default_factory=list)
    suspicious: list[str] = field(default_factory=list)
    judge_rc: int | None = None
    judge_output: str = ""
    judge_timed_out: bool = False
    canary: str = "none"
    dirty: bool = False
    end_sha: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def in_scope(path: str, scope: list[str]) -> bool:
    return any(path == s or path.startswith(s.rstrip("/") + "/") for s in scope)


def canary_for(item: Item, checkout: Path) -> tuple[Path, str] | None:
    """A test file that the judge must FAIL on, or None when none can be derived.

    Explicit `judge.canary {path, content}` wins. Otherwise `unittest discover` (honouring -s/-p)
    and pytest on a directory are recognised. A `-k` filter disables derivation.
    """
    c = item.judge.canary
    if c and c.get("path") and c.get("content"):
        return checkout / str(c["path"]), str(c["content"])
    try:
        toks = shlex.split(item.judge.cmd)
    except ValueError:
        toks = item.judge.cmd.split()
    if "-k" in toks or any(t.startswith("-k=") for t in toks):
        return None
    nonce = secrets.token_hex(4)
    if "unittest" in toks and "discover" in toks:
        start, pattern = ".", "test*.py"
        for i, t in enumerate(toks):
            if t in ("-s", "--start-directory") and i + 1 < len(toks):
                start = toks[i + 1]
            elif t.startswith("--start-directory="):
                start = t.split("=", 1)[1]
            elif t in ("-p", "--pattern") and i + 1 < len(toks):
                pattern = toks[i + 1]
            elif t.startswith("--pattern="):
                pattern = t.split("=", 1)[1]
        if "*" not in pattern or not (checkout / start).is_dir():
            return None
        name = pattern.replace("*", f"zz_{nonce}", 1)
        if not fnmatch.fnmatch(name, pattern):
            return None
        return checkout / start / name, UNITTEST_CANARY
    if "pytest" in toks:
        args = [t for t in toks[toks.index("pytest") + 1:] if not t.startswith("-")]
        dirs = [a for a in args if (checkout / a).is_dir()]
        files = [a for a in args if (checkout / a).is_file()]
        if files and not dirs:
            return None
        target = dirs[0] if dirs else ("tests" if (checkout / "tests").is_dir() else ".")
        return checkout / target / f"test_zz_{nonce}.py", PYTEST_CANARY
    return None


def judge_state(item: Item, lock_info: LockInfo, worktree: str | Path, rev: str,
                tmp_root: str | Path | None = None) -> JudgeOutcome:
    """Execute the judge in a fresh detached checkout of `rev`, judge files from the contract,
    then the canary run when the first run was green."""
    tmp = Path(tempfile.mkdtemp(prefix="ap-judge-", dir=str(tmp_root) if tmp_root else None))
    wt = tmp / "judge"
    gitx.worktree_add(worktree, wt, rev)
    try:
        for p in item.judge.paths:
            dest = wt / p
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(gitx.show_bytes(worktree, lock_info.contract_commit, p))
            entry = gitx.ls_tree_entry(worktree, lock_info.contract_commit, p)
            if entry and entry[0] == "100755":
                dest.chmod(0o755)
        r = run_shell(item.judge.cmd, wt, item.judge.timeout_s)
        if r.rc != 0:
            return JudgeOutcome(False, r.rc, r.tail(80), r.timed_out, "none",
                                "judge_timed_out" if r.timed_out else "judge_red")
        canary = canary_for(item, wt)
        if canary is None:
            return JudgeOutcome(True, 0, r.tail(80), False, "none", "")
        path, content = canary
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        c = run_shell(item.judge.cmd, wt, item.judge.timeout_s)
        path.unlink(missing_ok=True)
        if c.rc == 0:
            return JudgeOutcome(False, 0, r.tail(60) + "\n[autopilot] the judge also exited 0 with a failing canary test present:\n"
                                + c.tail(20), False, "broken", "judge_oracle_broken")
        return JudgeOutcome(True, 0, r.tail(80), False, "ok", "")
    finally:
        gitx.worktree_remove(worktree, wt)
        shutil.rmtree(tmp, ignore_errors=True)


def suspicious_additions(worktree: str | Path, start: str, end: str) -> list[str]:
    """Added lines mentioning things an implementer has no business touching (deviation only)."""
    hits: list[str] = []
    current = ""
    for line in gitx.out(worktree, "diff", "-U0", start, end, check=False).splitlines():
        if line.startswith("+++ "):
            current = line[4:].removeprefix("b/")
        elif line.startswith("+") and not line.startswith("+++"):
            for tok in SUSPICIOUS:
                if tok in line:
                    hits.append(f"{current}: {tok}")
    return sorted(set(hits))


def judge_attempt(plan: Plan, item: Item, lock_info: LockInfo, worktree: str | Path, start_sha: str,
                  session: SessionResult, branch: str | None = None, tmp_root: str | Path | None = None,
                  log: Callable[[str], None] | None = None) -> Verdict:
    log = log or (lambda s: None)
    v = Verdict()
    bad = verify_ref(lock_info, worktree)
    if bad:
        v.reasons.append("contract_ref_tampered: " + bad)
        return v
    if branch:
        sym = gitx.out(worktree, "symbolic-ref", "-q", "HEAD", check=False)
        if sym != f"refs/heads/{branch}":
            v.reasons.append("branch_detached")
    end = gitx.head(worktree)
    v.end_sha = end
    v.dirty = gitx.is_dirty(worktree)
    if gitx.git(worktree, "merge-base", "--is-ancestor", start_sha, end, check=False).returncode != 0:
        v.reasons.append("history_rewritten")
        return v
    v.commits = len(gitx.commits_between(worktree, start_sha, end))
    if v.commits == 0:
        v.reasons.append("zero_commits")
    for p in item.judge.paths:
        if gitx.blob_sha(worktree, end, p) != gitx.blob_sha(worktree, lock_info.contract_commit, p):
            v.tampered.append(p)
    if v.tampered:
        v.reasons.append("judge_tampered")
    v.files_changed = gitx.changed_files(worktree, start_sha, end) if v.commits else []
    v.unapproved = [f for f in v.files_changed if not in_scope(f, item.scope)]
    if v.unapproved and plan.glob.scope_policy == "fail":
        v.reasons.append("out_of_scope")
    so = session.structured_output or {}
    claims = [str(c) for c in (so.get("commands_run") or [])]
    v.fake_receipts = fake_claims(claims, bash_commands(session.transcript_path))
    if v.fake_receipts and plan.glob.strict_receipts:
        v.reasons.append("fake_receipt")
    claimed = {str(f) for f in (so.get("files_changed") or [])}
    v.claim_mismatch = sorted(claimed ^ set(v.files_changed))
    if v.commits:
        v.suspicious = suspicious_additions(worktree, start_sha, end)
    if v.reasons:
        return v
    log(f"judge: running `{item.judge.cmd}` on {gitx.short(end)}")
    out = judge_state(item, lock_info, worktree, end, tmp_root)
    v.judge_rc, v.judge_output, v.judge_timed_out, v.canary = out.rc, out.output, out.timed_out, out.canary
    v.passed = out.passed
    if out.reason:
        v.reasons.append(out.reason)
    return v
