"""Lock the contract: plan.json plus every judge file into refs/contract/<plan_id>, sha256 per path.

The implementer never writes that ref. The orchestrator also keeps the contract commit sha
outside the repo (run_dir/lock.json) and refuses to judge if the ref no longer matches.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import gitx
from .plan import Plan, dumps, from_dict


@dataclass
class LockInfo:
    plan_id: str
    ref: str
    contract_commit: str
    base_sha: str
    sha256: dict[str, dict[str, str]] = field(default_factory=dict)   # item -> path -> hex

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2) + "\n")

    @classmethod
    def load(cls, path: str | Path) -> "LockInfo":
        return cls(**json.loads(Path(path).read_text()))


def lock(plan: Plan, repo: str | Path, run_dir: str | Path) -> LockInfo:
    base = gitx.rev_parse(repo, plan.base_sha)
    if not base:
        raise gitx.GitError(f"base_sha {plan.base_sha!r} does not resolve")
    plan.base_sha = base
    entries: dict[str, tuple[str, str]] = {}
    sha256: dict[str, dict[str, str]] = {}
    for it in plan.items:
        sha256[it.id] = {}
        for p in it.judge.paths:
            entry = gitx.ls_tree_entry(repo, base, p)
            if not entry:
                raise gitx.GitError(f"judge path {p} is not committed at {gitx.short(base)}")
            mode, blob = entry
            if mode not in ("100644", "100755"):
                raise gitx.GitError(f"judge path {p} is not a file (mode {mode})")
            digest = hashlib.sha256(gitx.show_bytes(repo, base, p)).hexdigest()
            it.judge.sha256[p] = digest
            sha256[it.id][p] = digest
            entries[p] = (mode, blob)
    plan_bytes = dumps(plan).encode()
    entries["plan.json"] = ("100644", gitx.hash_object(repo, plan_bytes))
    tree = gitx.write_tree(repo, entries)
    commit = gitx.commit_tree(repo, tree, f"contract {plan.plan_id} (base {gitx.short(base)})")
    gitx.update_ref(repo, plan.contract_ref, commit)

    run_dir = Path(run_dir)
    cdir = run_dir / "contract"
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "plan.json").write_bytes(plan_bytes)
    for path in entries:
        if path == "plan.json":
            continue
        dest = cdir / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(gitx.show_bytes(repo, commit, path))
    info = LockInfo(plan.plan_id, plan.contract_ref, commit, base, sha256)
    info.save(run_dir / "lock.json")
    return info


def load_locked(lock_info: LockInfo, repo: str | Path) -> Plan:
    """The plan as committed in the contract ref, never from a file an implementer could edit."""
    return from_dict(json.loads(gitx.show_bytes(repo, lock_info.contract_commit, "plan.json")))


def verify_ref(lock_info: LockInfo, repo: str | Path) -> str | None:
    """None if the ref still points at the locked commit, else a reason string."""
    now = gitx.rev_parse(repo, lock_info.ref)
    if now != lock_info.contract_commit:
        return f"{lock_info.ref} is {gitx.short(now)}, expected {gitx.short(lock_info.contract_commit)}"
    return None
