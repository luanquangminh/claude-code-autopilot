"""Git helpers. Every call is an argv list, never a shell string (paths may contain spaces)."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

ORCH_ENV = {"GIT_AUTHOR_NAME": "autopilot", "GIT_AUTHOR_EMAIL": "autopilot@local",
            "GIT_COMMITTER_NAME": "autopilot", "GIT_COMMITTER_EMAIL": "autopilot@local"}


class GitError(RuntimeError):
    pass


def git(repo: str | Path, *args: str, check: bool = True, env: dict[str, str] | None = None,
        input_bytes: bytes | None = None, timeout: float = 120) -> subprocess.CompletedProcess:
    p = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, input=input_bytes,
                       env={**os.environ, **ORCH_ENV, **(env or {})}, timeout=timeout)
    if check and p.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed ({p.returncode}): {p.stderr.decode(errors='replace').strip()}")
    return p


def out(repo: str | Path, *args: str, **kw) -> str:
    return git(repo, *args, **kw).stdout.decode(errors="replace").strip()


def rev_parse(repo, rev: str) -> str | None:
    p = git(repo, "rev-parse", "--verify", "-q", rev, check=False)
    s = p.stdout.decode().strip()
    return s or None


def head(repo) -> str:
    sha = rev_parse(repo, "HEAD")
    if not sha:
        raise GitError("no HEAD")
    return sha


def tree_of(repo, rev: str) -> str | None:
    return rev_parse(repo, f"{rev}^{{tree}}")


def exists_at(repo, rev: str, path: str) -> bool:
    return git(repo, "cat-file", "-e", f"{rev}:{path}", check=False).returncode == 0


def blob_sha(repo, rev: str, path: str) -> str | None:
    return rev_parse(repo, f"{rev}:{path}")


def ls_tree_entry(repo, rev: str, path: str) -> tuple[str, str] | None:
    """(mode, sha) of a path at rev, or None."""
    s = out(repo, "ls-tree", rev, "--", path, check=False)
    for line in s.splitlines():
        meta, _, name = line.partition("\t")
        if name == path:
            parts = meta.split()
            return parts[0], parts[2]
    return None


def show_bytes(repo, rev: str, path: str) -> bytes:
    return git(repo, "show", f"{rev}:{path}").stdout


def commits_between(repo, a: str, b: str) -> list[str]:
    s = out(repo, "rev-list", f"{a}..{b}")
    return s.split() if s else []


def changed_files(repo, a: str, b: str) -> list[str]:
    s = out(repo, "diff", "--name-only", a, b)
    return [l for l in s.splitlines() if l]


def is_dirty(repo) -> bool:
    return bool(out(repo, "status", "--porcelain"))


def reset_hard(repo, rev: str) -> None:
    git(repo, "reset", "--hard", "-q", rev)
    git(repo, "clean", "-fdq")


def branch_exists(repo, name: str) -> bool:
    return rev_parse(repo, f"refs/heads/{name}") is not None


def worktree_add(repo, path: str | Path, rev: str, new_branch: str | None = None,
                 branch: str | None = None) -> None:
    args = ["worktree", "add"]
    if new_branch:
        args += ["-b", new_branch, str(path), rev]
    elif branch:
        args += [str(path), branch]
    else:
        args += ["--detach", str(path), rev]
    git(repo, *args)


def worktree_remove(repo, path: str | Path) -> None:
    git(repo, "worktree", "remove", "--force", str(path), check=False)
    git(repo, "worktree", "prune", check=False)


def hash_object(repo, data: bytes) -> str:
    return git(repo, "hash-object", "-w", "--stdin", input_bytes=data).stdout.decode().strip()


def write_tree(repo, entries: dict[str, tuple[str, str]]) -> str:
    """entries: path -> (mode, blob sha). Builds a tree through a temporary index."""
    fd, idx = tempfile.mkstemp(prefix="ap-index-")
    os.close(fd)
    os.unlink(idx)
    env = {"GIT_INDEX_FILE": idx}
    try:
        git(repo, "read-tree", "--empty", env=env)
        for path, (mode, sha) in sorted(entries.items()):
            git(repo, "update-index", "--add", "--cacheinfo", f"{mode},{sha},{path}", env=env)
        return out(repo, "write-tree", env=env)
    finally:
        if os.path.exists(idx):
            os.unlink(idx)


def commit_tree(repo, tree: str, message: str, parents: tuple[str, ...] = ()) -> str:
    args = ["commit-tree", tree]
    for p in parents:
        args += ["-p", p]
    args += ["-m", message]
    return out(repo, *args)


def update_ref(repo, ref: str, sha: str) -> None:
    git(repo, "update-ref", ref, sha)


def commit_paths(repo, paths: list[str], message: str) -> str:
    git(repo, "add", "-A", "--", *paths)
    git(repo, "commit", "-q", "-m", message, "--", *paths)
    return head(repo)


def short(sha: str | None) -> str:
    return (sha or "")[:7]
