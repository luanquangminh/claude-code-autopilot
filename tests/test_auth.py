"""Subscription-only sessions: key variables never reach a session; a session that reports a key stops the run."""
import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from autopilot.gitx import head
from autopilot.lock import lock
from autopilot.loop import Run
from autopilot.sessions import plan_pipeline
from tests.helpers import fake_run_config, fake_session_config, full_run, make_plan, make_repo, pager_item


class SubscriptionOnlyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_key_variables_are_scrubbed_from_sessions(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test", "ANTHROPIC_AUTH_TOKEN": "t"}):
            plan, info, repo, cfg, state = full_run(self.root, "b-scope", [pager_item(stop_line=2)], ["fix_pager"])
        self.assertEqual(state["status"], "done")
        self.assertEqual(state["items"][0]["status"], "green")
        self.assertEqual(state["items"][0]["attempts"][0]["session"]["api_key_source"], "none")

    def test_session_that_used_a_key_halts_the_run(self):
        with mock.patch.dict(os.environ, {"FAKE_CLAUDE_KEY_SOURCE": "apiKeyHelper"}):
            plan, info, repo, cfg, state = full_run(self.root, "b-scope", [pager_item(stop_line=3)], ["fix_pager", "fix_pager"])
        self.assertEqual(state["status"], "halted")
        self.assertIn("API key (apiKeyHelper)", state["halt_reason"])
        self.assertIn("--allow-api-key", state["halt_reason"])
        self.assertEqual(len(state["items"][0]["attempts"]), 1)      # no second session was started

    def test_allow_api_key_lets_a_key_session_run(self):
        repo = make_repo("b-scope", self.root / "repo")
        plan = make_plan("t-key", head(repo), [pager_item(stop_line=2)])
        cfg = fake_run_config(self.root, ["fix_pager"])
        cfg.auth = "api-key"
        info = lock(plan, repo, cfg.run_dir)
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            state = Run(plan, info, repo, cfg).run()
        self.assertEqual(state["status"], "done")
        self.assertEqual(state["items"][0]["status"], "green")
        self.assertEqual(state["items"][0]["attempts"][0]["session"]["api_key_source"], "ANTHROPIC_API_KEY")

    def test_plan_stage_refuses_a_key_session(self):
        repo = make_repo("b-scope", self.root / "repo")
        cfg = fake_session_config(self.root, ["draft_plan", "review"])
        with mock.patch.dict(os.environ, {"FAKE_CLAUDE_KEY_SOURCE": "ANTHROPIC_API_KEY"}):
            plan, problems, reviews, cost = plan_pipeline("fix pager", repo, "p1", cfg, self.root / "planning",
                                                          log=lambda s: None)
        self.assertIsNone(plan)
        self.assertEqual([p.code for p in problems], ["api_key_used"])
        self.assertEqual(reviews, [])


if __name__ == "__main__":
    unittest.main()
