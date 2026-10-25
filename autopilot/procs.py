"""Run a shell command with a wall-clock cap; kill the whole process group on timeout."""
from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CmdResult:
    rc: int | None
    output: str
    timed_out: bool
    duration_s: float

    def tail(self, lines: int = 60) -> str:
        parts = self.output.splitlines()
        return "\n".join(parts[-lines:])


def kill_group(proc: subprocess.Popen, grace_s: float = 5.0) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=grace_s)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()


def run_shell(cmd: str, cwd: str | Path, timeout_s: float, env: dict[str, str] | None = None) -> CmdResult:
    """bash -c <cmd> in cwd. stdout+stderr merged. Never raises on non-zero exit."""
    t0 = time.monotonic()
    proc = subprocess.Popen(["bash", "-c", cmd], cwd=str(cwd), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            start_new_session=True, env={**os.environ, **(env or {})})
    try:
        out, _ = proc.communicate(timeout=timeout_s)
        return CmdResult(proc.returncode, out or "", False, time.monotonic() - t0)
    except subprocess.TimeoutExpired:
        kill_group(proc)
        try:
            out, _ = proc.communicate(timeout=5)   # a grandchild may still hold the pipe
        except subprocess.TimeoutExpired:
            out = ""
        finally:
            if proc.stdout:
                proc.stdout.close()
        return CmdResult(None, (out or "") + f"\n[autopilot] timed out after {timeout_s}s",
                         True, time.monotonic() - t0)
    except BaseException:
        kill_group(proc)
        raise
