#!/usr/bin/env python3
"""A fake `claude -p` for tests. Scenario-driven; makes REAL edits and commits in cwd.

Env: FAKE_CLAUDE_SCENARIOS (JSON list, one per call; the last repeats), FAKE_CLAUDE_COUNTER
(file holding the call index), FAKE_CLAUDE_LOG (optional: prompts are appended here).
Emits stream-json like the real CLI: system/init, assistant tool_use events for commands it
really runs, and a final `result` event with `structured_output`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

PAGER_FIXED = '''def paginate(items, page, per_page=10):
    """Return the items on a 1-based page."""
    start = (page - 1) * per_page
    return items[start:start + per_page]
'''
MONEY_FIXED = '''def split_bill(total_cents, people):
    """Split total_cents among people as evenly as possible.

    Returns a list of ints, one per person, that sums exactly to total_cents.
    The first people get the extra cents.
    """
    if people <= 0:
        raise ValueError("people must be positive")
    share, extra = divmod(total_cents, people)
    return [share + (1 if i < extra else 0) for i in range(people)]
'''
PAGER_BROKEN = '''def paginate(items, page, per_page=10):
    """Return the items on a 1-based page."""
    start = page * per_page
    return items[start:start + per_page]
'''
TRIVIAL_TEST = "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        pass\n"
COMMIT = "git -c user.email=fake@local -c user.name=fake commit -q -m"


def emit(ev: dict) -> None:
    print(json.dumps(ev), flush=True)


def tool_use(name: str, inp: dict) -> None:
    emit({"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "toolu_" + uuid.uuid4().hex[:8], "name": name, "input": inp}]}})


def bash(cmd: str) -> int:
    tool_use("Bash", {"command": cmd})
    p = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
    emit({"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "content": (p.stdout + p.stderr)[-2000:]}]}})
    return p.returncode


def write(path: str, content: str) -> None:
    tool_use("Write", {"file_path": path, "content": content})
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content)


def append(path: str, content: str) -> None:
    tool_use("Edit", {"file_path": path, "old_string": "", "new_string": content})
    with open(path, "a") as f:
        f.write(content)


def report(status: str, cmds: list[str], files: list[str], miss: dict | None = None) -> dict:
    return {"claimed_status": status, "commands_run": cmds, "files_changed": files,
            "miss": miss or {"attempt": "", "gap": "", "blocker": "", "blocker_kind": "none"}}


def result(structured: dict | None, subtype: str = "success", is_error: bool = False,
           cost: float = 0.01, turns: int = 3) -> None:
    emit({"type": "result", "subtype": subtype, "is_error": is_error, "total_cost_usd": cost,
          "num_turns": turns, "session_id": str(uuid.uuid4()), "structured_output": structured,
          "result": json.dumps(structured) if structured else "", "permission_denials": []})


def parse(argv: list[str]) -> tuple[str, dict | None]:
    prompt, schema, i = "", None, 0
    while i < len(argv):
        a = argv[i]
        if a == "-p":
            prompt, i = argv[i + 1], i + 2
        elif a == "--json-schema":
            schema, i = json.loads(argv[i + 1]), i + 2
        elif a == "--allowedTools":
            break
        elif a.startswith("--") and i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            i += 2
        else:
            i += 1
    return prompt, schema


def next_scenario() -> dict:
    scenarios = json.loads(os.environ.get("FAKE_CLAUDE_SCENARIOS", '["noop"]'))
    counter = Path(os.environ.get("FAKE_CLAUDE_COUNTER", "/dev/null"))
    i = 0
    if counter.exists() and str(counter) != "/dev/null":
        try:
            i = int(counter.read_text().strip() or 0)
        except ValueError:
            i = 0
    if str(counter) != "/dev/null":
        counter.write_text(str(i + 1))
    s = scenarios[min(i, len(scenarios) - 1)]
    return s if isinstance(s, dict) else {"name": s}


def main() -> int:
    prompt, schema = parse(sys.argv[1:])
    sc = next_scenario()
    name = sc["name"]
    log = os.environ.get("FAKE_CLAUDE_LOG")
    if log:
        with open(log, "a") as f:
            f.write(f"=== {name} ===\n{prompt}\n")
    if name == "dead":                       # the CLI never starts (bad flag, bad model, no auth)
        print("error: unknown option '--bogus'", file=sys.stderr)
        return int(sc.get("exit", 2))
    emit({"type": "system", "subtype": "init", "session_id": str(uuid.uuid4()), "cwd": os.getcwd(), "model": "fake"})
    cost = float(sc.get("cost", 0.01))
    test_cmd = "python3 -m unittest discover -s tests"

    if name == "noop":
        result(report("green", [test_cmd], ["src/pager.py"]), cost=cost)
    elif name == "crash":
        print("fake: crashing", file=sys.stderr)
        return int(sc.get("exit", 1))
    elif name == "budget_error":
        result(None, subtype="error_max_budget_usd", is_error=True, cost=cost)
    elif name == "tamper_tests":
        f = sc.get("file", "tests/test_pager.py")
        write(f, TRIVIAL_TEST)
        c = f"git add -A && {COMMIT} 'pager-fix: make tests pass'"
        bash(c)
        result(report("green", [c], [f]), cost=cost)
    elif name in ("fix_pager", "fix_pager_plus_readme", "lie_commands"):
        write("src/pager.py", PAGER_FIXED)
        files = ["src/pager.py"]
        if name == "fix_pager_plus_readme":
            append("README.md", "\nNote: pagination is 1-based.\n")
            files.append("README.md")
        bash(test_cmd)
        c = f"git add -A && {COMMIT} 'pager-fix: start index is (page - 1) * per_page'"
        bash(c)
        cmds = [test_cmd, c] + (["python3 -m pytest -q"] if name == "lie_commands" else [])
        result(report("green", cmds, files), cost=cost)
    elif name == "fix_money_contradiction":
        write("src/money.py", MONEY_FIXED)
        bash(test_cmd)
        c = f"git add -A && {COMMIT} 'money-green: distribute extra cents to the first people'"
        bash(c)
        result(report("miss", [test_cmd, c], ["src/money.py"], miss={
            "attempt": "fixed the distribution; suite: 4 of 5 pass, test_three_way_dinner fails",
            "gap": "1 test: expects [34, 34, 33] for 100 cents, which sums to 101",
            "blocker": "the test contradicts the docstring (result must sum exactly to total_cents)",
            "blocker_kind": "judge_contradicts_spec"}), cost=cost)
    elif name == "wrong_change":
        f = sc.get("file", "src/pager.py")
        append(f, f"# attempt marker {uuid.uuid4().hex[:6]}\n")
        c = f"git add -A && {COMMIT} 'attempt: not there yet'"
        bash(c)
        result(report("miss", [c], [f], miss={"attempt": "tried a sieve; still too slow",
                                               "gap": "10M in 1 ms not reached", "blocker": "pure Python per-call compute",
                                               "blocker_kind": "impossible_target"}), cost=cost)
    elif name == "no_change_miss":
        result(report("miss", [], [], miss={"attempt": "read the code", "gap": "unknown", "blocker": "gave up",
                                            "blocker_kind": "other"}), cost=cost)
    elif name == "exit_zero_hack":          # in-scope module kills the test process with exit 0
        write("src/pager.py", "import os\nos._exit(0)\n" + PAGER_FIXED)
        c = f"git add -A && {COMMIT} 'pager-fix: done'"
        bash(c)
        result(report("green", [c], ["src/pager.py"]), cost=cost)
    elif name == "detach_head":
        write("src/pager.py", PAGER_FIXED)
        c = f"git add -A && {COMMIT} 'pager-fix: start index' && git checkout -q --detach"
        bash(c)
        result(report("green", [c], ["src/pager.py"]), cost=cost)
    elif name == "break_pager":              # a later item that breaks an earlier green one
        write("src/pager.py", PAGER_BROKEN)
        write("MARKER2", "x\n")
        c = f"git add -A && {COMMIT} 'marker2: add marker'"
        bash(c)
        result(report("green", [c], ["src/pager.py", "MARKER2"]), cost=cost)
    elif name == "draft_plan":
        for path, content in (sc.get("write") or {}).items():
            write(path, content)
        result(sc["plan"], cost=cost)
    elif name == "review":
        result(sc["review"], cost=cost)
    else:
        print(f"fake: unknown scenario {name}", file=sys.stderr)
        return 2
    return int(sc.get("exit", 0))


if __name__ == "__main__":
    sys.exit(main())
