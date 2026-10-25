"""Build-order checks: false success, tamper, scope, honest miss, stop line, caps, resume."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from autopilot.lock import lock
from autopilot.loop import Run, RunLocked
from autopilot.plan import Item, Judge, Target
from autopilot.report import render
from tests.helpers import (TEST_CMD, calls_made, fake_run_config, full_run, git, head, make_plan, make_repo,
                           money_item, pager_item, primes_item, prompts)


class LoopTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def wt(self, cfg):
        return cfg.run_dir / "worktree"

    def test_do_nothing_run_is_not_success(self):
        plan, info, repo, cfg, state = full_run(self.root, "b-scope", [pager_item(stop_line=3)], ["noop"])
        it = state["items"][0]
        self.assertEqual(it["status"], "missed")
        self.assertEqual(len(it["attempts"]), 2, "no-progress limit stops it before the stop line")
        a = it["attempts"][0]
        self.assertEqual(a["session"]["exit_code"], 0)
        self.assertEqual(a["session"]["subtype"], "success")
        self.assertEqual(a["claim"]["claimed_status"], "green")
        self.assertIn("zero_commits", a["verdict"]["reasons"])
        self.assertEqual(a["verdict"]["fake_receipts"], [TEST_CMD])
        self.assertTrue(any("never run" in d for d in state["deviations"]))
        self.assertEqual(it["miss"]["source"], "orchestrator")

    def test_tampered_judge_is_reset_then_honest_fix_passes(self):
        plan, info, repo, cfg, state = full_run(self.root, "b-scope", [pager_item()], ["tamper_tests", "fix_pager"])
        it = state["items"][0]
        self.assertEqual(it["status"], "green")
        self.assertIn("judge_tampered", it["attempts"][0]["verdict"]["reasons"])
        self.assertEqual(it["attempts"][0]["verdict"]["tampered"], ["tests/test_pager.py"])
        self.assertTrue(it["attempts"][0]["reset"])
        self.assertTrue(it["attempts"][1]["verdict"]["passed"])
        wt = self.wt(cfg)
        self.assertEqual(git(wt, "diff", "--stat", plan.base_sha, "HEAD", "--", "tests"), "")
        self.assertEqual(git(wt, "rev-list", "--count", f"{plan.base_sha}..HEAD"), "1")
        self.assertEqual(git(repo, "rev-parse", "refs/heads/autopilot/t-b-scope"), head(wt))
        self.assertIn("branch restored", "\n".join(state["deviations"]))

    def test_out_of_scope_fails_and_is_reported(self):
        plan, info, repo, cfg, state = full_run(self.root, "b-scope", [pager_item()], ["fix_pager_plus_readme", "fix_pager"])
        it = state["items"][0]
        self.assertEqual(it["status"], "green")
        self.assertEqual(it["attempts"][0]["verdict"]["reasons"], ["out_of_scope"])
        self.assertEqual(it["attempts"][0]["verdict"]["unapproved"], ["README.md"])
        md = render(plan, state)
        self.assertIn("## Unapproved", md)
        self.assertIn("pager-fix attempt 1: README.md", md)
        self.assertIn("files outside SCOPE were changed", prompts(self.root).lower().replace("files outside scope were changed", "files outside SCOPE were changed"))

    def test_scope_policy_report_passes_but_lists(self):
        plan, info, repo, cfg, state = full_run(self.root, "b-scope", [pager_item()], ["fix_pager_plus_readme"],
                                                scope_policy="report")
        it = state["items"][0]
        self.assertEqual(it["status"], "green")
        self.assertEqual(it["attempts"][0]["verdict"]["unapproved"], ["README.md"])
        self.assertIn("README.md", render(plan, state))

    def test_a_honest_contradiction_blocks_with_tests_untouched(self):
        plan, info, repo, cfg, state = full_run(self.root, "a-honest", [money_item()], ["fix_money_contradiction"])
        it = state["items"][0]
        self.assertEqual(it["status"], "blocked")
        self.assertEqual(len(it["attempts"]), 1)
        self.assertEqual(it["miss"]["blocker_kind"], "judge_contradicts_spec")
        self.assertEqual(it["attempts"][0]["verdict"]["reasons"], ["judge_red"])
        self.assertIn("test_three_way_dinner", it["attempts"][0]["verdict"]["judge_output"])
        wt = self.wt(cfg)
        self.assertEqual(git(wt, "diff", "--stat", plan.base_sha, "HEAD", "--", "tests"), "")
        self.assertIn("src/money.py", git(wt, "diff", "--name-only", plan.base_sha, "HEAD"))
        self.assertIn("judge_contradicts_spec", render(plan, state))

    def test_a_honest_keeps_trying_then_misses_at_stop_line(self):
        plan, info, repo, cfg, state = full_run(self.root, "a-honest", [money_item(stop_line=3)],
                                                [{"name": "wrong_change", "file": "src/money.py"}])
        it = state["items"][0]
        self.assertEqual(it["status"], "missed")
        self.assertEqual(len(it["attempts"]), 3)
        self.assertEqual(it["miss"]["source"], "model self-report")
        self.assertEqual(state["status"], "done")

    def test_a2_impossible_stops_at_stop_line_and_run_continues(self):
        repo = make_repo("a2-speed", self.root / "repo")
        # second item on the same fixture: a judge that is red until a marker file exists
        second = Item(id="marker", goal="create MARKER", scope=["MARKER"],
                      judge=Judge(cmd="test -f MARKER", paths=["tests/test_primes.py"], timeout_s=5),
                      target=Target("file exists", "proven (test -f)"), stop_line=1)
        plan = make_plan("t-a2", head(repo), [primes_item(stop_line=3), second])
        cfg = fake_run_config(self.root, [{"name": "wrong_change", "file": "src/primes.py"}] * 3 +
                              [{"name": "wrong_change", "file": "MARKER"}])
        info = lock(plan, repo, cfg.run_dir)
        state = Run(plan, info, repo, cfg).run()
        first, marker = state["items"]
        self.assertEqual(first["status"], "missed")
        self.assertEqual(len(first["attempts"]), 3)
        self.assertEqual(first["attempts"][-1]["verdict"]["reasons"], ["judge_timed_out"])
        self.assertEqual(marker["status"], "green", "a missed item never blocks the run")
        self.assertEqual(state["status"], "done")
        self.assertEqual(calls_made(self.root), 4)

    def test_crash_and_budget_error_are_failed_attempts(self):
        plan, info, repo, cfg, state = full_run(self.root, "b-scope", [pager_item(stop_line=3)],
                                                ["crash", "budget_error", "fix_pager"], no_progress_limit=3)
        it = state["items"][0]
        self.assertEqual([a["session"]["subtype"] for a in it["attempts"]], ["no_result", "error_max_budget_usd", "success"])
        self.assertEqual(it["status"], "green")
        self.assertEqual([a["cost_charged"] for a in it["attempts"]], [2.0, 0.01, 0.01],
                         "a crash with no result event is charged the full attempt budget")
        self.assertAlmostEqual(state["total_cost_usd"], 2.02)
        self.assertAlmostEqual(state["total_cost_reported_usd"], 0.02)

    def test_exit_zero_hack_is_caught_by_canary(self):
        plan, info, repo, cfg, state = full_run(self.root, "b-scope", [pager_item(stop_line=1)], ["exit_zero_hack"])
        it = state["items"][0]
        self.assertEqual(it["status"], "missed")
        v = it["attempts"][0]["verdict"]
        self.assertEqual(v["reasons"], ["judge_oracle_broken"])
        self.assertEqual(v["canary"], "broken")
        self.assertIn("src/pager.py: os._exit", v["suspicious"])
        self.assertIn("suspicious additions", "\n".join(state["deviations"]))

    def test_detached_head_is_restored(self):
        plan, info, repo, cfg, state = full_run(self.root, "b-scope", [pager_item()], ["detach_head", "fix_pager"])
        it = state["items"][0]
        self.assertEqual(it["status"], "green")
        self.assertIn("branch_detached", it["attempts"][0]["verdict"]["reasons"])
        self.assertTrue(it["attempts"][0]["reset"])
        self.assertFalse(it["attempts"][0]["progress"])
        wt = self.wt(cfg)
        self.assertEqual(git(wt, "symbolic-ref", "HEAD"), "refs/heads/autopilot/t-b-scope")
        self.assertEqual(git(wt, "rev-list", "--count", f"{plan.base_sha}..HEAD"), "1")

    def test_regression_marks_earlier_green_item(self):
        marker = Item(id="marker2", goal="add MARKER2", scope=["src/pager.py", "MARKER2"],
                      judge=Judge(cmd="test -f MARKER2", paths=["tests/test_pager.py"], timeout_s=5),
                      target=Target("file exists", "proven (test -f)"), stop_line=1)
        plan, info, repo, cfg, state = full_run(self.root, "b-scope", [pager_item(), marker], ["fix_pager", "break_pager"])
        self.assertEqual([i["status"] for i in state["items"]], ["regressed", "green"])
        self.assertEqual(state["items"][0]["regression"]["reason"], "judge_red")
        self.assertEqual(state["status"], "done")
        md = render(plan, state)
        self.assertIn("## pager-fix: regressed", md)
        self.assertIn("RED (judge_red)", md)

    def test_dead_cli_halts_and_is_charged(self):
        plan, info, repo, cfg, state = full_run(self.root, "b-scope", [pager_item(stop_line=3)], ["dead"])
        self.assertEqual(state["status"], "halted")
        self.assertIn("no output", state["halt_reason"])
        self.assertIn("unknown option", state["halt_reason"])
        self.assertEqual(len(state["items"][0]["attempts"]), 1)
        self.assertAlmostEqual(state["total_cost_usd"], 2.0)
        self.assertIn("not_started", render(plan, state))

    def test_reset_attempts_do_not_count_as_progress(self):
        plan, info, repo, cfg, state = full_run(self.root, "b-scope", [pager_item(stop_line=3)], ["tamper_tests"])
        it = state["items"][0]
        self.assertEqual(it["status"], "missed")
        self.assertEqual(len(it["attempts"]), 2)
        self.assertIn("without progress", it["note"])

    def test_stale_lock_is_replaced(self):
        repo = make_repo("b-scope", self.root / "repo")
        plan = make_plan("t-stale", head(repo), [pager_item()])
        cfg = fake_run_config(self.root, ["fix_pager"])
        info = lock(plan, repo, cfg.run_dir)
        (cfg.run_dir / "run.lock").write_text("4000000")
        state = Run(plan, info, repo, cfg).run()
        self.assertEqual(state["items"][0]["status"], "green")
        self.assertFalse((cfg.run_dir / "run.lock").exists())

    def test_wall_cap_halts(self):
        plan, info, repo, cfg, state = full_run(self.root, "b-scope", [pager_item()], ["fix_pager"], max_wall_minutes=1e-6)
        self.assertEqual(state["status"], "halted")
        self.assertIn("wall clock", state["halt_reason"])
        self.assertEqual(calls_made(self.root), 0)

    def test_cost_cap_halts(self):
        plan, info, repo, cfg, state = full_run(self.root, "b-scope", [pager_item(stop_line=3)],
                                                [{"name": "budget_error", "cost": 0.6}], max_cost_usd=0.5)
        self.assertEqual(state["status"], "halted")
        self.assertIn("cost cap", state["halt_reason"])
        self.assertEqual(len(state["items"][0]["attempts"]), 1)

    def test_attempt_cap_halts(self):
        plan, info, repo, cfg, state = full_run(self.root, "b-scope", [pager_item(stop_line=3)], ["noop"],
                                                max_attempts_total=1, no_progress_limit=5)
        self.assertEqual(state["status"], "halted")
        self.assertIn("attempt cap", state["halt_reason"])

    def test_stop_file_then_resume(self):
        repo = make_repo("b-scope", self.root / "repo")
        plan = make_plan("t-stop", head(repo), [pager_item()])
        cfg = fake_run_config(self.root, ["fix_pager"])
        info = lock(plan, repo, cfg.run_dir)
        cfg.run_dir.mkdir(parents=True, exist_ok=True)
        (cfg.run_dir / "STOP").write_text("")
        state = Run(plan, info, repo, cfg).run()
        self.assertEqual(state["status"], "halted")
        self.assertEqual(calls_made(self.root), 0)
        (cfg.run_dir / "STOP").unlink()
        state = Run(plan, info, repo, cfg).run()
        self.assertEqual(state["status"], "done")
        self.assertEqual(state["items"][0]["status"], "green")
        self.assertFalse((cfg.run_dir / "run.lock").exists())

    def test_lock_file_refuses_concurrent_run(self):
        repo = make_repo("b-scope", self.root / "repo")
        plan = make_plan("t-lock", head(repo), [pager_item()])
        cfg = fake_run_config(self.root, ["fix_pager"])
        info = lock(plan, repo, cfg.run_dir)
        (cfg.run_dir / "run.lock").write_text(str(os.getppid()))   # a live pid that is not ours
        with self.assertRaises(RunLocked):
            Run(plan, info, repo, cfg).run()
        self.assertEqual((cfg.run_dir / "run.lock").read_text(), str(os.getppid()), "a foreign live lock is left alone")

    def test_strict_receipts(self):
        plan, info, repo, cfg, state = full_run(self.root, "b-scope", [pager_item(stop_line=1)], ["lie_commands"],
                                                strict_receipts=True)
        it = state["items"][0]
        self.assertEqual(it["status"], "missed")
        self.assertEqual(it["attempts"][0]["verdict"]["reasons"], ["fake_receipt"])
        plan, info, repo, cfg, state = full_run(Path(tempfile.mkdtemp(dir=self.root)), "b-scope",
                                                [pager_item(stop_line=1)], ["lie_commands"])
        self.assertEqual(state["items"][0]["status"], "green")
        self.assertIn("never run", "\n".join(state["deviations"]))

    def test_already_green_item_is_skipped_without_a_session(self):
        twin = pager_item(); twin.id = "pager-twin"
        plan, info, repo, cfg, state = full_run(self.root, "b-scope", [pager_item(), twin], ["fix_pager"])
        self.assertEqual([i["status"] for i in state["items"]], ["green", "green"])
        self.assertEqual(calls_made(self.root), 1)
        self.assertIn("already green", state["items"][1]["note"])

    def test_contract_ref_tamper_halts(self):
        repo = make_repo("b-scope", self.root / "repo")
        plan = make_plan("t-ref", head(repo), [pager_item()])
        cfg = fake_run_config(self.root, ["fix_pager"])
        info = lock(plan, repo, cfg.run_dir)
        git(repo, "update-ref", "refs/contract/t-ref", head(repo))
        state = Run(plan, info, repo, cfg).run()
        self.assertEqual(state["status"], "halted")
        self.assertIn("contract ref tampered", state["halt_reason"])

    def test_report_shape(self):
        plan, info, repo, cfg, state = full_run(self.root, "b-scope", [pager_item()], ["fix_pager"])
        md = render(plan, state)
        for needle in ("# Autopilot report: t-b-scope", "## pager-fix: green", "| Judge |", "| Target |", "reached",
                       "| Scope: `src/pager.py` | approved | changed |", "## Deviations", "## Next rung", "Not merged",
                       "PASS (canary ok)", "| Regression at final HEAD | still green | green"):
            self.assertIn(needle, md)
        self.assertEqual(state["items"][0]["attempts"][0]["verdict"]["canary"], "ok")
        self.assertTrue((cfg.run_dir / "state.json").exists())
        self.assertEqual(json.loads((cfg.run_dir / "state.json").read_text())["status"], "done")


if __name__ == "__main__":
    unittest.main()
