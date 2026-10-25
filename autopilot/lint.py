"""Plan lint: git-level checks plus the rule that every judge is RED on the baseline."""
from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import gitx
from .plan import Plan, validate
from .procs import run_shell


@dataclass
class Problem:
    code: str
    detail: str
    item: str | None = None

    def __str__(self) -> str:
        return f"[{self.item or 'plan'}] {self.code}: {self.detail}"


def overlaps(a: str, b: str) -> bool:
    a, b = a.strip("/"), b.strip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def lint(plan: Plan, repo: str | Path, run_judges: bool = True, tmp_root: str | Path | None = None,
         log: Callable[[str], None] | None = None) -> list[Problem]:
    log = log or (lambda s: None)
    problems = [Problem("schema", m) for m in validate(plan)]
    if problems:
        return problems
    base = gitx.rev_parse(repo, plan.base_sha)
    if not base:
        return [Problem("base_sha", f"{plan.base_sha!r} does not resolve in {repo}")]
    for it in plan.items:
        for p in it.judge.paths:
            entry = gitx.ls_tree_entry(repo, base, p)
            if not entry or p.endswith("/"):
                problems.append(Problem("judge_path_missing", f"{p} is not committed at {gitx.short(base)}", it.id))
            elif entry[0] not in ("100644", "100755"):
                problems.append(Problem("judge_path_not_file", f"{p} is mode {entry[0]} at {gitx.short(base)}; judge paths must be files", it.id))
        for s in it.scope:
            for j in it.judge.paths:
                if overlaps(s, j):
                    problems.append(Problem("scope_overlaps_judge", f"scope {s} overlaps judge path {j}", it.id))
    if problems or not run_judges:
        return problems
    tmp = Path(tempfile.mkdtemp(prefix="ap-lint-", dir=str(tmp_root) if tmp_root else None))
    wt = tmp / "base"
    gitx.worktree_add(repo, wt, base)
    try:
        for it in plan.items:
            log(f"lint: running judge for {it.id} on baseline {gitx.short(base)}")
            r = run_shell(it.judge.cmd, wt, it.judge.timeout_s)
            if r.rc == 0:
                problems.append(Problem("judge_green_on_baseline",
                                        f"`{it.judge.cmd}` exits 0 at {gitx.short(base)}: a vacuous judge", it.id))
            elif r.timed_out:
                log(f"lint: judge for {it.id} timed out on baseline ({it.judge.timeout_s}s); counted as red")
    finally:
        gitx.worktree_remove(repo, wt)
        shutil.rmtree(tmp, ignore_errors=True)
    return problems
