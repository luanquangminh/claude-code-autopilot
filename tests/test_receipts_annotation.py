import unittest

from autopilot.receipts import fake_claims


class TrailingAnnotationTest(unittest.TestCase):
    CMDS = ["git reset -q --hard HEAD~1", "python3 -m unittest discover -s tests"]

    def test_trailing_parenthetical_is_ignored(self):
        self.assertEqual(fake_claims(["git reset -q --hard HEAD~1 (denied, not executed)"], self.CMDS), [])
        self.assertEqual(fake_claims(["python3 -m unittest discover -s tests  (all 12 passed)"], self.CMDS), [])

    def test_annotated_claim_with_unrun_command_is_still_flagged(self):
        claim = "python3 -m pytest -q (passed)"
        self.assertEqual(fake_claims([claim], self.CMDS), [claim])
        claim = "git push origin main (denied)"
        self.assertEqual(fake_claims([claim], self.CMDS), [claim])

    def test_plain_claims_unchanged(self):
        self.assertEqual(fake_claims(["git reset -q --hard HEAD~1"], self.CMDS), [])
        self.assertEqual(fake_claims(["git push"], self.CMDS), ["git push"])


if __name__ == "__main__":
    unittest.main()
