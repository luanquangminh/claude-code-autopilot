"""Subscription-only sessions: key variables never reach a session; a session that reports a key stops the run."""
import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from autopilot.sessions import plan_pipeline
from tests.helpers import fake_session_config, full_run, head, make_repo, pager_item


class SubscriptionOnlyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_key_variables_are_scrubbed_from_sessions(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test", "ANTHROPIC_AUTH_TOKEN": "t"}):
            *_, state = full_run(self.root, "b-scope", [pager_item(stop_line=2)], ["fix_pager"])
        self.assertEqual(state["status"], "done")
        self.assertEqual(state["items"][0]["status"], "green")
        self.assertEqual(state["items"][0]["attempts"][0]["session"]["api_key_source"], "none")

    def test_session_that_used_a_key_halts_the_run(self):
        with mock.patch.dict(os.environ, {"FAKE_CLAUDE_KEY_SOURCE": "apiKeyHelper"}):
            *_, state = full_run(self.root, "b-scope", [pager_item(stop_line=3)], ["fix_pager", "fix_pager"])
        self.assertEqual(state["status"], "halted")
        self.assertIn("API key (apiKeyHelper)", state["halt_reason"])
        self.assertIn("--allow-api-key", state["halt_reason"])
        self.assertEqual(len(state["items"][0]["attempts"]), 1)      # no second session was started

    def test_allow_api_key_lets_a_key_session_run(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            *_, state = full_run(self.root, "b-scope", [pager_item(stop_line=2)], ["fix_pager"], cfg={"allow_api_key": True})
        self.assertEqual(state["status"], "done")
        self.assertEqual(state["items"][0]["status"], "green")
        self.assertEqual(state["items"][0]["attempts"][0]["session"]["api_key_source"], "ANTHROPIC_API_KEY")

    def test_plan_stage_refuses_a_key_session(self):
        repo = make_repo("b-scope", self.root / "repo")
        base = head(repo)
        cfg = fake_session_config(self.root, ["draft_plan", "review"])
        with mock.patch.dict(os.environ, {"FAKE_CLAUDE_KEY_SOURCE": "ANTHROPIC_API_KEY"}):
            plan, problems, reviews, cost = plan_pipeline("fix pager", repo, "p1", cfg, self.root / "planning",
                                                          log=lambda s: None)
        self.assertEqual([p.code for p in problems], ["api_key_used"])
        self.assertEqual(reviews, [])
        self.assertEqual(head(repo), base)       # the refused draft's judge files were never committed


if __name__ == "__main__":
    unittest.main()
