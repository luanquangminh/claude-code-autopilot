"""Shared test helpers: fixture repos from ambition-skill/evals, hand-written plans, the fake claude."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from autopilot.loop import Run, RunConfig
from autopilot.lock import lock
from autopilot.plan import Global, Item, Judge, Plan, Target
from autopilot.runner import SessionConfig

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"  # copied from samhvw8/ambition-skill evals/<case>/fixture (MIT)
FAKE = ROOT / "tests" / "fake_claude.py"
TEST_CMD = "python3 -m unittest discover -s tests"


def make_repo(case: str, dest: Path) -> Path:
    shutil.copytree(FIXTURES / case, dest, dirs_exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=dest, check=True)
    subprocess.run(["git", "add", "-A"], cwd=dest, check=True)
    subprocess.run(["git", "-c", "user.email=t@local", "-c", "user.name=t", "commit", "-q", "-m", "fixture"],
                   cwd=dest, check=True)
    return dest


def head(repo: Path) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def pager_item(stop_line: int = 2, **kw) -> Item:
    return Item(id="pager-fix", goal="paginate() page 1 returns the first items", scope=["src/pager.py"],
                judge=Judge(cmd=TEST_CMD, paths=["tests/test_pager.py"], timeout_s=60),
                target=Target("2/2 tests", "proven (tests/test_pager.py)"), stop_line=stop_line, **kw)


def money_item(stop_line: int = 3) -> Item:
    return Item(id="money-green", goal="whole suite green", scope=["src/money.py"],
                judge=Judge(cmd=TEST_CMD, paths=["tests/test_money.py"], timeout_s=60),
                target=Target("5/5 tests", "proven (tests/test_money.py)"), stop_line=stop_line)


def primes_item(stop_line: int = 3) -> Item:
    return Item(id="primes-fast", goal="count_primes(10_000_000) in under 1 ms", scope=["src/primes.py"],
                judge=Judge(cmd="python3 -m unittest discover -s tests -p test_primes.py -k ten_million",
                            paths=["tests/test_primes.py"], timeout_s=5),
                target=Target("10M below 1 ms", "unreasonable on purpose"), stop_line=stop_line)


def make_plan(plan_id: str, base: str, items: list[Item], **glob) -> Plan:
    g = Global(**{"max_cost_usd": 20.0, "attempt_timeout_s": 60, **glob})
    return Plan(plan_id=plan_id, base_sha=base, items=items, glob=g, task="test task")


def fake_env(tmp: Path, scenarios: list) -> dict[str, str]:
    return {"FAKE_CLAUDE_SCENARIOS": json.dumps(scenarios), "FAKE_CLAUDE_COUNTER": str(tmp / "counter"),
            "FAKE_CLAUDE_LOG": str(tmp / "prompts.log")}


def fake_run_config(tmp: Path, scenarios: list) -> RunConfig:
    return RunConfig(run_dir=tmp / "run", claude_cmd=[sys.executable, str(FAKE)], env=fake_env(tmp, scenarios),
                     tmp_root=tmp, log=lambda s: None, max_turns=10)


def fake_session_config(tmp: Path, scenarios: list) -> SessionConfig:
    return SessionConfig(claude_cmd=[sys.executable, str(FAKE)], env=fake_env(tmp, scenarios), timeout_s=60)


def calls_made(tmp: Path) -> int:
    c = tmp / "counter"
    return int(c.read_text()) if c.exists() else 0


def prompts(tmp: Path) -> str:
    p = tmp / "prompts.log"
    return p.read_text() if p.exists() else ""


def full_run(tmp: Path, case: str, items: list[Item], scenarios: list, **glob):
    repo = make_repo(case, tmp / "repo")
    plan = make_plan(f"t-{case}", head(repo), items, **glob)
    cfg = fake_run_config(tmp, scenarios)
    info = lock(plan, repo, cfg.run_dir)
    state = Run(plan, info, repo, cfg).run()
    return plan, info, repo, cfg, state
