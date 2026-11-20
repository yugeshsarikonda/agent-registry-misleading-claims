"""Guard against corrupted releases, split leakage and silently changed results."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_release", ROOT / "analysis" / "verify_release.py")
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class SplitTests(unittest.TestCase):
    def test_valid_partition(self):
        self.assertEqual(verifier.validate_split({"calibration": [0], "evaluation": [1]}, {0, 1}),
                         ({0}, {1}))

    def test_rejects_leakage_missing_unknown_duplicate_and_empty_tasks(self):
        splits = [
            {"calibration": [0], "evaluation": [0, 1]},
            {"calibration": [0], "evaluation": [1, 1]},
            {"calibration": [0], "evaluation": [2]},
            {"calibration": [0], "evaluation": []},
            {"calibration": [0], "evaluation": ["1"]},
            {"calibration": [False], "evaluation": [1]},
        ]
        for split in splits:
            with self.subTest(split=split), self.assertRaises(ValueError):
                verifier.validate_split(split, {0, 1})
        with self.assertRaisesRegex(ValueError, "cover"):
            verifier.validate_split({"calibration": [0], "evaluation": [1]}, {0, 1, 2})


class TrialTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(task_id="1", chosen_provider="P2", chosen_slot="B", order="P1|P2|P3|P4",
                        parsed="1", realised_correct="1.0")
        self.competence = {(1, "P2"): 1}

    def test_unreadable_trials_remain_in_denominator(self):
        unreadable = dict(self.row, parsed="0", chosen_slot="", chosen_provider="", realised_correct="")
        self.assertEqual(verifier.validate_trials([self.row, unreadable], {1}, self.competence, "test"),
                         {"attempted": 2, "readable": 1})

    def test_rejects_invalid_readable_records(self):
        changes = [dict(task_id="0"), dict(parsed="2"), dict(chosen_provider="P5"),
                   dict(realised_correct="0"), dict(realised_correct="nan"), dict(chosen_slot="E"),
                   dict(chosen_slot="A"), dict(order="P1|P2|P2|P4")]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                verifier.validate_trials([dict(self.row, **change)], {1}, self.competence, "test")

    def test_unreadable_calibration_task_cannot_enter_heldout_trials(self):
        with self.assertRaisesRegex(ValueError, "outside allowed split"):
            verifier.validate_trials([dict(self.row, task_id="0", parsed="0")], {1}, self.competence, "test")

    def test_empty_trials_fail_instead_of_reporting_success(self):
        with self.assertRaisesRegex(ValueError, "No trials"):
            verifier.validate_trials([], {1}, self.competence, "test")


class CompetenceTests(unittest.TestCase):
    def setUp(self):
        self.rows = [dict(task_id="1", provider=p, truth="42", answer="42", parsed="1", correct="1")
                     for p in sorted(verifier.PROVIDERS)]

    def test_checks_all_four_providers_against_ground_truth(self):
        self.assertEqual(len(verifier.validate_competence(self.rows, {1: 42})), 4)

    def test_rejects_incomplete_duplicate_or_misscored_measurements(self):
        bad_score = copy.deepcopy(self.rows)
        bad_score[0]["answer"] = "41"
        for rows in (self.rows[:-1], self.rows + self.rows[:1], bad_score):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                verifier.validate_competence(rows, {1: 42})

    def test_unparsed_answer_cannot_count_as_correct(self):
        self.rows[0].update(parsed="0", answer="", correct="0")
        self.assertEqual(verifier.validate_competence(self.rows, {1: 42})[1, "P1"], 0)
        self.rows[0]["correct"] = "1"
        with self.assertRaisesRegex(ValueError, "answer/score"):
            verifier.validate_competence(self.rows, {1: 42})


class ResultComparisonTests(unittest.TestCase):
    def test_allows_roundoff_and_equivalent_csv_number_formatting(self):
        verifier.compare_values({"rows": ["1.000000000001", "P1"]}, {"rows": ["1", "P1"]}, "results")

    def test_rejects_changed_counts_missing_rows_and_nonfinite_results(self):
        for actual in ({"n": 2}, {"n": float("nan")}, {}, {"n": 1, "extra": 0}):
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                verifier.compare_values(actual, {"n": 1}, "results")
        with self.assertRaisesRegex(ValueError, "Row count"):
            verifier.compare_values([], [1], "results")


class IntegrityTests(unittest.TestCase):
    def test_detects_tampering_missing_files_and_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "records.csv"
            target.write_bytes(b"frozen records\n")
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            manifest = {"algorithm": "sha256", "files": {"records.csv": digest}}
            (root / "SHA256SUMS.json").write_text(json.dumps(manifest))
            self.assertEqual(verifier.verify_integrity(root), 1)
            target.write_bytes(b"altered records\n")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                verifier.verify_integrity(root)
            target.unlink()
            with self.assertRaisesRegex(ValueError, "Missing snapshot"):
                verifier.verify_integrity(root)
            manifest["files"] = {"../outside.csv": digest}
            (root / "SHA256SUMS.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "escapes release"):
                verifier.verify_integrity(root)


class ReleasedDataTests(unittest.TestCase):
    def test_actual_snapshot_passes_all_integrity_and_split_checks(self):
        result = verifier.verify()
        self.assertEqual(result["status"], "passed")
        self.assertEqual((result["calibration_tasks"], result["evaluation_tasks"]), (30, 29))
        self.assertEqual(result["trial_checks"]["heldout_screening.csv"],
                         {"attempted": 348, "readable": 337})


if __name__ == "__main__":
    unittest.main()
