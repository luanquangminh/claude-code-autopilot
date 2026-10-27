"""canary_for() on compound judge commands (&&, ||, ;)."""
import tempfile
import unittest
from fnmatch import fnmatch
from pathlib import Path

from autopilot.judge import canary_for
from autopilot.plan import Item, Judge, Target


def item(cmd: str) -> Item:
    return Item(id="x", goal="g", scope=["a.py"], judge=Judge(cmd=cmd, paths=[]),
                target=Target("1", "guess (no baseline)"))


class CompoundCanaryTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.co = Path(self._td.name)
        for d in ("tests", "a", "b", "other"):
            (self.co / d).mkdir()

    def parent_of(self, cmd: str):
        got = canary_for(item(cmd), self.co)
        return None if got is None else got[0].parent.name

    def test_k_in_earlier_segment_is_ignored(self):
        self.assertEqual(self.parent_of("grep -k foo x.txt && python3 -m unittest discover -s tests"), "tests")

    def test_s_p_in_later_segment_are_ignored(self):
        self.assertEqual(self.parent_of("python3 -m unittest discover -s tests && sort -s -p x"), "tests")
        self.assertEqual(self.parent_of("python3 -m unittest discover -s tests; ls -s other"), "tests")

    def test_first_recognised_segment_wins(self):
        self.assertEqual(self.parent_of(
            "python3 -m unittest discover -s a || python3 -m unittest discover -s b"), "a")
        self.assertEqual(self.parent_of(
            "echo hi && python3 -m unittest discover -s b && python3 -m unittest discover -s a"), "b")

    def test_pattern_comes_from_the_chosen_segment(self):
        got = canary_for(item("python3 -m unittest discover -s a -p 'check*.py' && ls -p 'q*.py'"), self.co)
        self.assertIsNotNone(got)
        self.assertEqual(got[0].parent.name, "a")
        self.assertTrue(fnmatch(got[0].name, "check*.py"), got[0].name)

    def test_pytest_directory_in_compound(self):
        got = canary_for(item("make -k && python3 -m pytest other"), self.co)
        self.assertIsNotNone(got)
        self.assertEqual(got[0].parent.name, "other")
        self.assertTrue(got[0].name.startswith("test_zz_"))

    def test_k_in_the_recognised_segment_still_disables(self):
        self.assertIsNone(canary_for(item("python3 -m unittest discover -s tests -k foo && echo ok"), self.co))

    def test_no_recognised_segment(self):
        self.assertIsNone(canary_for(item("echo hi && ls; true"), self.co))

    def test_simple_command_unchanged(self):
        self.assertEqual(self.parent_of("python3 -m unittest discover -s tests -t ."), "tests")


if __name__ == "__main__":
    unittest.main()
