"""Journey 定義と実行報告の整合性に関する回帰テスト。"""

import pathlib
import tempfile
import unittest
from unittest import mock

import run_matrix


class VerdictTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actions = run_matrix.load_journey_actions(run_matrix.JOURNEY_DIR / "J01.journey.xml")

    def report(self, count=None, failed_index=None):
        count = len(self.actions) if count is None else count
        return [
            {"index": index, "action": action,
             "status": "FAILED" if index == failed_index else "PASSED"}
            for index, action in enumerate(self.actions[:count], start=1)
        ]

    def assert_error(self, steps):
        verdict, error = run_matrix.derive_verdict(steps, self.actions)
        self.assertEqual(verdict, "ERROR")
        self.assertTrue(error)

    def test_complete_success_is_pass(self):
        self.assertEqual(run_matrix.derive_verdict(self.report(), self.actions), ("PASS", ""))

    def test_successful_prefix_is_not_pass(self):
        for count in range(1, len(self.actions)):
            with self.subTest(reported_steps=count):
                verdict, error = run_matrix.derive_verdict(self.report(count), self.actions)
                self.assertEqual(verdict, "ERROR")
                self.assertIn("不足", error)

    def test_failure_can_end_the_report_early(self):
        for failed_index in range(1, len(self.actions) + 1):
            with self.subTest(failed_step=failed_index):
                steps = self.report(failed_index, failed_index)
                self.assertEqual(run_matrix.derive_verdict(steps, self.actions), ("FAIL", ""))

    def test_complete_report_with_failure_is_fail(self):
        steps = self.report(failed_index=3)
        self.assertEqual(run_matrix.derive_verdict(steps, self.actions), ("FAIL", ""))

    def test_duplicate_reordered_and_changed_actions_are_errors(self):
        for label, replacement in [("duplicate", self.actions[0]), ("changed", "別の操作")]:
            with self.subTest(case=label):
                steps = self.report()
                steps[1]["action"] = replacement
                self.assert_error(steps)
        steps = self.report()
        steps[0]["action"], steps[1]["action"] = steps[1]["action"], steps[0]["action"]
        self.assert_error(steps)

    def test_missing_step_before_failure_is_error(self):
        steps = self.report(3, failed_index=3)
        del steps[1]
        self.assert_error(steps)

    def test_extra_steps_are_error(self):
        steps = self.report()
        steps.append({"index": len(steps) + 1, "action": "追加の操作", "status": "PASSED"})
        self.assert_error(steps)

    def test_empty_report_and_unknown_status_are_errors(self):
        self.assert_error([])
        steps = self.report()
        steps[2]["status"] = "SKIPPED"
        self.assert_error(steps)

    def test_whitespace_differences_are_accepted(self):
        steps = self.report()
        for step in steps:
            step["action"] = " \n" + step["action"] + "\n  "
        self.assertEqual(run_matrix.derive_verdict(steps, self.actions), ("PASS", ""))

    def test_definition_controls_required_step_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "two_steps.journey.xml"
            path.write_text(
                '<journey><actions><action>商品 &amp; 数量</action>'
                '<action>注文を確認する</action></actions></journey>', encoding="utf-8",
            )
            actions = run_matrix.load_journey_actions(path)
            self.assertEqual(actions, ["商品 & 数量", "注文を確認する"])
            steps = [{"index": i, "action": action, "status": "PASSED"}
                     for i, action in enumerate(actions, start=1)]
            self.assertEqual(run_matrix.derive_verdict(steps, actions), ("PASS", ""))
            self.assertEqual(run_matrix.derive_verdict(steps[:1], actions)[0], "ERROR")

    def test_empty_definition_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "empty.journey.xml"
            path.write_text('<journey><actions /></journey>', encoding="utf-8")
            with self.assertRaises(ValueError):
                run_matrix.load_journey_actions(path)
        self.assertEqual(run_matrix.derive_verdict(self.report(), [])[0], "ERROR")

    def test_malformed_result_entry_is_not_silently_dropped(self):
        payload = {"results": self.report() + [None]}
        with tempfile.TemporaryDirectory() as directory:
            steps = run_matrix.normalize_steps(payload, pathlib.Path(directory), 0)
            self.assert_error(steps)

    def test_execute_cell_once_checks_the_report_against_the_journey(self):
        class FixedMockRunner(run_matrix.MockRunner):
            def __init__(self, steps):
                super().__init__({"tiers": {"high": {"model": "test-model"}}})
                self.steps = steps

            def execute_mock(self, cell, journey_path, workdir):
                return {"journey": cell.case_id, "results": self.steps}

        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            apk = root / "test.apk"
            apk.write_bytes(b"mock")
            cases = [
                (self.report(1), "ERROR"),
                (self.report(3, failed_index=3), "FAIL"),
                (self.report(), "PASS"),
            ]
            with mock.patch.object(run_matrix, "ROOT", root):
                for trial, (steps, expected) in enumerate(cases, start=1):
                    with self.subTest(verdict=expected):
                        result = run_matrix.execute_cell_once(
                            cell=run_matrix.Cell("J01", "clean", "high", "PASS"),
                            trial=trial, apk=apk, runner=FixedMockRunner(steps),
                            prompt_template="", prompt_sha="test", device=None,
                            workdir_base=root / "workdir", results_dir=root / "results",
                            dry_run=True,
                        )
                        self.assertEqual(result.verdict, expected)
                        if expected == "ERROR":
                            self.assertIn("不足", result.error)
                        else:
                            self.assertEqual(result.error, "")


if __name__ == "__main__":
    unittest.main()
