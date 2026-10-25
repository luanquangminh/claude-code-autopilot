import json
import tempfile
import unittest
from pathlib import Path

from autopilot.receipts import bash_commands, fake_claims, matches


class ReceiptsTest(unittest.TestCase):
    def test_matches_is_ordered_subsequence(self):
        self.assertTrue(matches("python3 -m unittest", "cd x && python3 -m unittest discover -s tests"))
        self.assertFalse(matches("python3 -m pytest", "python3 -m unittest discover"))
        self.assertFalse(matches("unittest python3", "python3 -m unittest"))
        self.assertFalse(matches("", "python3 -m unittest"))

    def test_multiline_commit_and_pipes_still_match(self):
        claim = 'git add src/pager.py && git commit -q -m "pager-fix: use 1-based offset" && git log --oneline -1'
        real = ('git add src/pager.py && git commit -q -m "pager-fix: use 1-based offset\n\n'
                'Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" && git log --oneline -1')
        self.assertTrue(matches(claim, real))
        self.assertTrue(matches("python3 -m unittest discover -s tests 2>&1 | tail -5",
                                "python3 -m unittest discover -s tests 2>&1 | tail -5"))
        self.assertFalse(matches(claim, 'git commit -q -m "other message"'))

    def test_fake_claims_and_transcript(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d) / "t.jsonl"
            t.write_text("\n".join([
                json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "python3   -m unittest discover -s tests"}}]}}),
                json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "I ran pytest"}]}}),
                "not json",
            ]))
            cmds = bash_commands(t)
            self.assertEqual(cmds, ["python3 -m unittest discover -s tests"])
            fakes = fake_claims(["python3 -m unittest discover -s tests", "python3 -m pytest -q", "git commit <msg>", ""], cmds)
            self.assertEqual(fakes, ["python3 -m pytest -q"])
        self.assertEqual(bash_commands(Path(d) / "missing.jsonl"), [])


if __name__ == "__main__":
    unittest.main()
