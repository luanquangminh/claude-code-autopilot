"""Bad --repo / plan arguments must give one `FAIL ` line on stdout and exit 2, never a traceback."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from autopilot.plan import to_dict
from tests.helpers import ROOT, pager_item, make_plan


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "autopilot", *args], cwd=ROOT, capture_output=True,
                          text=True, timeout=60)


class CliErrorTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.tmp = Path(self._td.name)
        self.plan = self.tmp / "plan.json"
        self.plan.write_text(json.dumps(to_dict(make_plan("t-cli", "", [pager_item()]))))
        self.notgit = self.tmp / "notgit"
        self.notgit.mkdir()

    def check(self, *args: str):
        r = run_cli(*args)
        label = " ".join(args)
        self.assertNotIn("Traceback", r.stderr, label)
        self.assertEqual(r.returncode, 2, f"{label}\n{r.stdout}\n{r.stderr}")
        lines = r.stdout.strip().splitlines()
        self.assertEqual(len(lines), 1, f"{label}: {r.stdout!r}")
        self.assertTrue(lines[0].startswith("FAIL "), f"{label}: {lines[0]!r}")

    def test_repo_does_not_exist(self):
        missing = str(self.tmp / "nope")
        for cmd in ("lint", "lock", "run", "review"):
            with self.subTest(cmd=cmd):
                self.check(cmd, str(self.plan), "--repo", missing)
        with self.subTest(cmd="plan"):
            self.check("plan", "do a thing", "--repo", missing)

    def test_repo_is_not_git(self):
        for cmd in ("lint", "lock", "run", "review"):
            with self.subTest(cmd=cmd):
                self.check(cmd, str(self.plan), "--repo", str(self.notgit))
        with self.subTest(cmd="plan"):
            self.check("plan", "do a thing", "--repo", str(self.notgit))

    def test_plan_file_missing(self):
        for cmd in ("lint", "lock", "run", "review"):
            with self.subTest(cmd=cmd):
                self.check(cmd, str(self.tmp / "absent.json"), "--repo", str(ROOT))

    def test_plan_file_not_json(self):
        bad = self.tmp / "bad.json"
        bad.write_text("{not json")
        for cmd in ("lint", "lock", "run", "review"):
            with self.subTest(cmd=cmd):
                self.check(cmd, str(bad), "--repo", str(ROOT))


if __name__ == "__main__":
    unittest.main()
