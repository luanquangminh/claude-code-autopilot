import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from autopilot import plan as planmod
from autopilot.lint import lint, overlaps
from autopilot.lock import LockInfo, lock, verify_ref
from autopilot.plan import Judge, Target
from tests.helpers import TEST_CMD, git, head, make_plan, make_repo, pager_item


class PlanSchemaTest(unittest.TestCase):
    def test_round_trip_and_defaults(self):
        p = make_plan("rt-1", "abc", [pager_item()])
        d = planmod.to_dict(p)
        self.assertEqual(d["items"][0]["judge"]["pass"], "exit 0")
        self.assertEqual(d["contract_ref"], "refs/contract/rt-1")
        q = planmod.from_dict(json.loads(planmod.dumps(p)))
        self.assertEqual(q.items[0].judge.cmd, TEST_CMD)
        self.assertEqual(q.glob.scope_policy, "fail")
        self.assertEqual(planmod.validate(q), [])

    def test_validate_catches_problems(self):
        p = make_plan("bad id!", "abc", [pager_item(stop_line=0), pager_item()])
        p.items[0].target = Target("x", "hopefully")
        p.glob.scope_policy = "whatever"
        msgs = "\n".join(planmod.validate(p))
        for needle in ("plan_id", "duplicate id", "stop_line", "target.state", "scope_policy"):
            self.assertIn(needle, msgs)
        self.assertIn("no items", "\n".join(planmod.validate(make_plan("x", "abc", []))))


class LintTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = make_repo("b-scope", self.root / "repo")
        self.base = head(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_overlaps(self):
        self.assertTrue(overlaps("tests", "tests/test_pager.py"))
        self.assertTrue(overlaps("tests/test_pager.py", "tests/"))
        self.assertFalse(overlaps("src/pager.py", "tests/test_pager.py"))

    def test_valid_plan_passes(self):
        self.assertEqual(lint(make_plan("ok", self.base, [pager_item()]), self.repo, tmp_root=self.root), [])

    def test_green_on_baseline_rejected(self):
        it = pager_item()
        it.judge = Judge(cmd="python3 -c pass", paths=["tests/test_pager.py"])
        probs = lint(make_plan("vac", self.base, [it]), self.repo, tmp_root=self.root)
        self.assertEqual([p.code for p in probs], ["judge_green_on_baseline"])

    def test_scope_overlap_and_missing_judge_path(self):
        a = pager_item(); a.scope = ["src/pager.py", "tests/"]
        b = pager_item(); b.id = "other"; b.judge = Judge(cmd=TEST_CMD, paths=["tests/nope.py"])
        probs = lint(make_plan("x", self.base, [a, b]), self.repo, tmp_root=self.root)
        self.assertEqual(sorted(p.code for p in probs), ["judge_path_missing", "scope_overlaps_judge"])

    def test_directory_judge_path_rejected(self):
        it = pager_item()
        it.judge = Judge(cmd=TEST_CMD, paths=["tests"])
        probs = lint(make_plan("d", self.base, [it]), self.repo, tmp_root=self.root)
        self.assertEqual([p.code for p in probs], ["judge_path_not_file"])
        it.judge = Judge(cmd=TEST_CMD, paths=["tests/"])
        probs = lint(make_plan("d", self.base, [it]), self.repo, tmp_root=self.root)
        self.assertEqual([p.code for p in probs], ["judge_path_missing"])

    def test_bad_base_sha(self):
        probs = lint(make_plan("x", "deadbeef", [pager_item()]), self.repo, tmp_root=self.root)
        self.assertEqual([p.code for p in probs], ["base_sha"])


class LockTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = make_repo("b-scope", self.root / "repo")
        self.base = head(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_lock_builds_ref_and_sha256(self):
        plan = make_plan("lk", self.base, [pager_item()])
        info = lock(plan, self.repo, self.root / "run")
        self.assertEqual(git(self.repo, "rev-parse", "refs/contract/lk"), info.contract_commit)
        locked = json.loads(git(self.repo, "show", "refs/contract/lk:plan.json"))
        want = hashlib.sha256(git(self.repo, "show", f"{self.base}:tests/test_pager.py").encode() + b"\n").hexdigest()
        # git show strips nothing; compare against the file bytes directly
        want = hashlib.sha256((self.repo / "tests" / "test_pager.py").read_bytes()).hexdigest()
        self.assertEqual(locked["items"][0]["judge"]["sha256"]["tests/test_pager.py"], want)
        self.assertEqual(info.sha256["pager-fix"]["tests/test_pager.py"], want)
        self.assertTrue((self.root / "run" / "contract" / "tests" / "test_pager.py").exists())
        self.assertEqual(LockInfo.load(self.root / "run" / "lock.json").contract_commit, info.contract_commit)
        self.assertIsNone(verify_ref(info, self.repo))
        git(self.repo, "update-ref", "refs/contract/lk", self.base)
        self.assertIn("expected", verify_ref(info, self.repo) or "")


if __name__ == "__main__":
    unittest.main()
