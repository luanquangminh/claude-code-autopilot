import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from autopilot.sessions import plan_pipeline
from tests.helpers import ROOT, TEST_CMD, calls_made, fake_session_config, git, make_repo, prompts

GOOD = {"plan_id": "x", "task": "fix pager", "next_rung": "paginate report.py too", "constraints": "",
        "items": [{"id": "pager-fix", "goal": "page 1 returns the first items", "scope": ["src/pager.py"],
                   "judge": {"cmd": TEST_CMD, "paths": ["tests/test_pager.py"]},
                   "target": {"value": "2/2", "state": "proven (tests/test_pager.py)"}, "stop_line": 2}]}
VACUOUS = {**GOOD, "items": [{**GOOD["items"][0], "judge": {"cmd": "python3 -c pass", "paths": ["tests/test_pager.py"]}}]}
CREEP = {**GOOD, "items": GOOD["items"] + [{"id": "csv-export", "goal": "CSV export", "scope": ["src/export.py"],
                                            "judge": {"cmd": "test -f src/export.py", "paths": ["tests/test_pager.py"]},
                                            "target": {"value": "1", "state": "guess (no baseline)"}, "stop_line": 1}]}
EXTRA_TEST = ("import sys, unittest\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))\n"
              "from pager import paginate\n\nclass E(unittest.TestCase):\n    def test_second(self):\n"
              "        self.assertEqual(paginate(list(range(25)), 2), list(range(10, 20)))\n")


def review(verdict, gaps=(), cut=(), notes=""):
    return {"name": "review", "review": {"verdict": verdict, "cut": list(cut), "gaps": list(gaps), "notes": notes}}


class PlanPipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = make_repo("b-scope", self.root / "repo")

    def tearDown(self):
        self.tmp.cleanup()

    def run_pipeline(self, scenarios):
        cfg = fake_session_config(self.root, scenarios)
        return plan_pipeline("fix pager", self.repo, "p1", cfg, self.root / "planning", log=lambda s: None)

    def test_lint_feedback_then_review_approve(self):
        plan, problems, reviews, cost = self.run_pipeline([
            {"name": "draft_plan", "plan": VACUOUS}, {"name": "draft_plan", "plan": GOOD}, review("approve")])
        self.assertEqual(problems, [])
        self.assertEqual(plan.plan_id, "p1")
        self.assertEqual(plan.base_sha, git(self.repo, "rev-parse", "HEAD"))
        self.assertIn("judge_green_on_baseline", prompts(self.root))
        self.assertEqual([r["verdict"] for r in reviews], ["approve"])
        self.assertEqual(calls_made(self.root), 3)
        self.assertAlmostEqual(cost, 0.03)

    def test_review_cuts_creep_and_high_gap_triggers_one_revision(self):
        plan, problems, reviews, cost = self.run_pipeline([
            {"name": "draft_plan", "plan": CREEP},
            review("revise", gaps=[{"item": "pager-fix", "severity": "high", "note": "cover page 2"}], cut=["csv-export"]),
            {"name": "draft_plan", "plan": {**GOOD, "items": [{**GOOD["items"][0], "judge": {"cmd": TEST_CMD, "paths": ["tests/test_pager.py", "tests/test_extra.py"]}}]},
             "write": {"tests/test_extra.py": EXTRA_TEST}},
            review("approve")])
        self.assertEqual(problems, [])
        self.assertEqual([it.id for it in plan.items], ["pager-fix"])
        self.assertEqual(plan.items[0].judge.paths, ["tests/test_pager.py", "tests/test_extra.py"])
        self.assertIn("contract: judge files for p1", git(self.repo, "log", "-1", "--format=%s"))
        self.assertIn("reviewer gap (pager-fix): cover page 2", prompts(self.root))
        self.assertEqual(calls_made(self.root), 4)

    def test_review_never_approves_is_a_problem(self):
        gap = [{"item": "pager-fix", "severity": "high", "note": "cover page 2"}]
        plan, problems, reviews, cost = self.run_pipeline([
            {"name": "draft_plan", "plan": GOOD}, review("revise", gaps=gap),
            {"name": "draft_plan", "plan": GOOD}, review("revise", gaps=gap)])
        self.assertIsNotNone(plan)
        self.assertEqual([p.code for p in problems], ["review_not_approved"])
        self.assertEqual(len(reviews), 2)
        (self.root / "counter").unlink()
        plan, problems, reviews, cost = self.run_pipeline([{"name": "draft_plan", "plan": GOOD}, "crash"])
        self.assertEqual([p.code for p in problems], ["review_not_approved"])
        self.assertEqual(reviews, [])

    def test_rounds_exhausted_returns_problems(self):
        plan, problems, reviews, cost = self.run_pipeline([{"name": "draft_plan", "plan": VACUOUS}])
        self.assertEqual([p.code for p in problems], ["judge_green_on_baseline"])
        self.assertEqual(reviews, [])


class CliSmokeTest(unittest.TestCase):
    def test_lint_and_run_via_cli(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            repo = make_repo("b-scope", root / "repo")
            plan_path = root / "plan.json"
            from autopilot.plan import save
            from tests.helpers import head, make_plan, pager_item
            save(make_plan("cli-1", "", [pager_item()]), plan_path)
            env = {**dict(__import__("os").environ), "FAKE_CLAUDE_SCENARIOS": '["fix_pager"]',
                   "FAKE_CLAUDE_COUNTER": str(root / "c"), "PYTHONPATH": str(ROOT)}
            import shlex
            fake = f"{shlex.quote(sys.executable)} {shlex.quote(str(ROOT / 'tests' / 'fake_claude.py'))}"
            r = subprocess.run([sys.executable, "-m", "autopilot", "lint", str(plan_path), "--repo", str(repo)],
                               capture_output=True, text=True, env=env, cwd=ROOT)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("every judge red", r.stdout)
            r = subprocess.run([sys.executable, "-m", "autopilot", "run", str(plan_path), "--repo", str(repo),
                                "--run-dir", str(root / "run"), "--claude-cmd", fake], capture_output=True, text=True, env=env, cwd=ROOT)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("## pager-fix: green", r.stdout)
            self.assertTrue((root / "run" / "report.md").exists())
            r = subprocess.run([sys.executable, "-m", "autopilot", "report", "--run-dir", str(root / "run")],
                               capture_output=True, text=True, env=env, cwd=ROOT)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("Not merged", r.stdout)
            env2 = {**env, "FAKE_CLAUDE_SCENARIOS": '["noop"]', "FAKE_CLAUDE_COUNTER": str(root / "c2")}
            plan2 = root / "plan2.json"
            save(make_plan("cli-2", "", [pager_item()]), plan2)
            r = subprocess.run([sys.executable, "-m", "autopilot", "run", str(plan2), "--repo", str(repo),
                                "--run-dir", str(root / "run2"), "--claude-cmd", fake], capture_output=True, text=True, env=env2, cwd=ROOT)
            self.assertEqual(r.returncode, 1, "done but not all green exits 1: " + r.stdout + r.stderr)
            # same plan id in a second run dir: the branch is busy elsewhere, so the run halts with a clear reason
            r = subprocess.run([sys.executable, "-m", "autopilot", "run", str(plan_path), "--repo", str(repo),
                                "--run-dir", str(root / "run3"), "--claude-cmd", fake], capture_output=True, text=True, env=env2, cwd=ROOT)
            self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
            self.assertIn("already checked out in another worktree", r.stderr + r.stdout)
            # relock in the first run dir archives the old state, worktree and branch
            r = subprocess.run([sys.executable, "-m", "autopilot", "run", str(plan_path), "--repo", str(repo),
                                "--run-dir", str(root / "run"), "--claude-cmd", fake, "--relock"], capture_output=True, text=True,
                               env={**env, "FAKE_CLAUDE_COUNTER": str(root / "c3")}, cwd=ROOT)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("archived previous run", r.stderr)
            self.assertTrue((root / "run" / "archive").exists())
            branches = subprocess.run(["git", "branch", "--list", "autopilot/cli-1*"], cwd=repo, capture_output=True, text=True).stdout
            self.assertEqual(branches.count("autopilot/cli-1"), 2)


if __name__ == "__main__":
    unittest.main()
