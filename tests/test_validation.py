from __future__ import annotations

import contextlib
import csv
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vlips_rf import create_demo, validate_artifact  # noqa: E402
from vlips_rf.cli import main as cli_main  # noqa: E402


class ArtifactCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "artifact"
        create_demo(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def read_segments(self) -> tuple[list[str], list[dict[str, str]]]:
        with (self.root / "segments.csv").open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            reader = csv.DictReader(handle)
            return list(reader.fieldnames or []), list(reader)

    def write_segments(
        self, fields: list[str], rows: list[dict[str, str]]
    ) -> None:
        with (self.root / "segments.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def issue_codes(self, report) -> set[str]:
        return {issue.code for issue in report.issues}


class ValidationConformanceTests(ArtifactCase):
    def test_demo_passes_l2_and_l4(self) -> None:
        l2 = validate_artifact(self.root, require_level="L2")
        l4 = validate_artifact(self.root, require_level="L4")
        self.assertTrue(l2.accepted)
        self.assertTrue(l4.accepted)
        self.assertEqual("L4", l4.highest_provable_level)

    def test_cross_role_source_overlap_fails_l0(self) -> None:
        fields, rows = self.read_segments()
        rows[2]["source_file_id"] = rows[0]["source_file_id"]
        rows[2]["sample_start"] = "1024"
        rows[2]["sample_end"] = "2048"
        self.write_segments(fields, rows)

        report = validate_artifact(self.root, require_level="L0")
        self.assertFalse(report.accepted)
        self.assertIn("E_INTERVAL_ROLE_OVERLAP", self.issue_codes(report))
        self.assertIn("E_SOURCE_ROLE_CROSSING", self.issue_codes(report))

    def test_identity_role_conflict_fails_l2(self) -> None:
        fields, rows = self.read_segments()
        rows[2]["physical_emitter_id"] = rows[0]["physical_emitter_id"]
        self.write_segments(fields, rows)

        report = validate_artifact(self.root, require_level="L2")
        self.assertFalse(report.accepted)
        self.assertEqual("L1", report.highest_provable_level)
        self.assertIn("E_IDENTITY_ROLE_CROSSING", self.issue_codes(report))

    def test_semantic_role_aliases_do_not_create_false_conflicts(self) -> None:
        fields, rows = self.read_segments()
        rows[1]["physical_emitter_id"] = rows[0]["physical_emitter_id"]
        rows[1]["role"] = "K"
        rows[0]["role"] = "train"
        self.write_segments(fields, rows)

        report = validate_artifact(self.root, require_level="L2")
        self.assertTrue(report.accepted)
        self.assertNotIn("E_IDENTITY_ROLE_CROSSING", self.issue_codes(report))

    def test_unresolved_evidence_caps_level(self) -> None:
        fields, rows = self.read_segments()
        rows[0]["evidence_level"] = "unresolved"
        self.write_segments(fields, rows)

        report = validate_artifact(self.root, require_level="L1")
        self.assertFalse(report.accepted)
        self.assertEqual("L0", report.highest_provable_level)
        self.assertIn("E_EVIDENCE_UNRESOLVED", self.issue_codes(report))

    def test_missing_pipeline_is_not_checkable_and_rejects_l3(self) -> None:
        (self.root / "pipeline_dependencies.json").unlink()
        report = validate_artifact(self.root, require_level="L3")
        payload = report.to_dict(explain=True)

        self.assertFalse(report.accepted)
        self.assertEqual("L2", report.highest_provable_level)
        issue = next(
            item
            for item in payload["issues"]
            if item["code"] == "E_PIPELINE_DEPENDENCIES_MISSING"
        )
        self.assertEqual("not_checkable", issue["status"])
        self.assertEqual("NOT_CHECKABLE", payload["checks"]["L3"]["status"])

    def test_missing_transition_caps_l3_and_rejects_l4(self) -> None:
        (self.root / "query_transitions.csv").unlink()
        report = validate_artifact(self.root, require_level="L4")

        self.assertFalse(report.accepted)
        self.assertEqual("L3", report.highest_provable_level)
        self.assertIn("E_QUERY_TRANSITIONS_MISSING", self.issue_codes(report))

    def test_same_version_query_update_rejects_l4(self) -> None:
        transition_path = self.root / "query_transitions.csv"
        with transition_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = list(reader.fieldnames or [])
            rows = list(reader)
        self.assertGreaterEqual(len(rows), 1, "the L4 demo must demonstrate a transition")
        rows[0]["to_model_version"] = rows[0]["from_model_version"]
        with transition_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

        report = validate_artifact(self.root, require_level="L4")
        self.assertFalse(report.accepted)
        self.assertEqual("L3", report.highest_provable_level)
        self.assertIn("E_QUERY_VERSION_NOT_ADVANCED", self.issue_codes(report))

    def test_non_fresh_query_transition_rejects_l4(self) -> None:
        transition_path = self.root / "query_transitions.csv"
        with transition_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = list(reader.fieldnames or [])
            rows = list(reader)
        rows[0]["fresh_relative_to_previous_versions"] = "false"
        with transition_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

        report = validate_artifact(self.root, require_level="L4")
        self.assertFalse(report.accepted)
        self.assertEqual("L3", report.highest_provable_level)
        self.assertIn("E_QUERY_NOT_FRESH", self.issue_codes(report))

    def test_same_version_pipeline_backwrite_rejects_l3(self) -> None:
        path = self.root / "pipeline_dependencies.json"
        pipeline = json.loads(path.read_text(encoding="utf-8"))
        pipeline["nodes"].append(
            {
                "id": "adapt-model-v1",
                "role": "train",
                "usage": "update",
                "model_version": "model-v1",
            }
        )
        pipeline["edges"].append(
            {"from": "evaluate-model-v1", "to": "adapt-model-v1"}
        )
        path.write_text(json.dumps(pipeline), encoding="utf-8")

        report = validate_artifact(self.root, require_level="L3")
        self.assertFalse(report.accepted)
        self.assertEqual("L2", report.highest_provable_level)
        self.assertIn("E_PIPELINE_BACKWRITE_SAME_VERSION", self.issue_codes(report))

    def test_u_role_alias_is_treated_as_held_out(self) -> None:
        path = self.root / "pipeline_dependencies.json"
        pipeline = json.loads(path.read_text(encoding="utf-8"))
        evaluate = next(node for node in pipeline["nodes"] if node["usage"] == "evaluate")
        evaluate["role"] = "U"
        pipeline["nodes"].append(
            {
                "id": "adapt-model-v1",
                "role": "K",
                "usage": "update",
                "model_version": "model-v1",
            }
        )
        pipeline["edges"].append(
            {"from": "evaluate-model-v1", "to": "adapt-model-v1"}
        )
        path.write_text(json.dumps(pipeline), encoding="utf-8")

        report = validate_artifact(self.root, require_level="L3")
        self.assertFalse(report.accepted)
        self.assertIn("E_PIPELINE_BACKWRITE_SAME_VERSION", self.issue_codes(report))

    def test_incomplete_pipeline_stage_coverage_is_not_checkable(self) -> None:
        path = self.root / "pipeline_dependencies.json"
        pipeline = json.loads(path.read_text(encoding="utf-8"))
        pipeline["nodes"] = pipeline["nodes"][:1]
        pipeline["edges"] = []
        path.write_text(json.dumps(pipeline), encoding="utf-8")

        report = validate_artifact(self.root, require_level="L3")
        payload = report.to_dict(explain=True)
        self.assertFalse(report.accepted)
        issue = next(
            item for item in payload["issues"]
            if item["code"] == "E_PIPELINE_STAGE_COVERAGE"
        )
        self.assertEqual("not_checkable", issue["status"])

    def test_report_has_stable_json_shape(self) -> None:
        payload = validate_artifact(self.root, require_level="L2").to_dict(explain=True)
        rendered = json.dumps(payload)
        decoded = json.loads(rendered)

        self.assertEqual("1.0", decoded["schema_version"])
        self.assertIs(decoded["accepted"], True)
        self.assertEqual("L2", decoded["required_level"])
        self.assertEqual("L4", decoded["highest_provable_level"])
        self.assertEqual(["L0", "L1", "L2", "L3", "L4"], list(decoded["checks"]))
        for check in decoded["checks"].values():
            self.assertIn(check["status"], {"PASS", "FAIL", "NOT_CHECKABLE"})
            self.assertIsInstance(check["passed"], bool)
        self.assertIsInstance(decoded["statistics"], dict)
        self.assertIsInstance(decoded["issues"], list)


class CliContractTests(ArtifactCase):
    def invoke(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli_main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_exit_zero_and_json_for_accepted_artifact(self) -> None:
        code, stdout, stderr = self.invoke(
            ["validate", str(self.root), "--require-level", "L2", "--format", "json"]
        )
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertTrue(json.loads(stdout)["accepted"])

    def test_exit_one_for_validation_rejection(self) -> None:
        fields, rows = self.read_segments()
        rows[2]["physical_emitter_id"] = rows[0]["physical_emitter_id"]
        self.write_segments(fields, rows)
        code, stdout, _ = self.invoke(
            ["validate", str(self.root), "--require-level", "L2", "--format", "json"]
        )
        self.assertEqual(1, code)
        self.assertFalse(json.loads(stdout)["accepted"])

    def test_exit_two_for_fatal_artifact_error(self) -> None:
        missing = Path(self.temporary.name) / "does-not-exist"
        code, stdout, stderr = self.invoke(
            ["validate", str(missing), "--require-level", "L0", "--format", "json"]
        )
        self.assertEqual(2, code)
        self.assertEqual("", stderr)
        payload = json.loads(stdout)
        self.assertFalse(payload["accepted"])
        self.assertEqual("E_ARTIFACT_DIRECTORY", payload["fatal"]["code"])

    def test_report_option_writes_machine_readable_report(self) -> None:
        report_path = Path(self.temporary.name) / "reports" / "validation.json"
        code, _, _ = self.invoke(
            [
                "validate",
                str(self.root),
                "--require-level",
                "L2",
                "--format",
                "json",
                "--report",
                str(report_path),
            ]
        )
        self.assertEqual(0, code)
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertTrue(payload["accepted"])
        self.assertEqual("1.0", payload["schema_version"])

    def test_config_path_escape_is_fatal(self) -> None:
        config_path = self.root / "vlips.yaml"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["files"]["segments"] = "../outside.csv"
        config_path.write_text(json.dumps(config), encoding="utf-8")

        code, stdout, _ = self.invoke(
            ["validate", str(self.root), "--require-level", "L0", "--format", "json"]
        )
        self.assertEqual(2, code)
        self.assertEqual("E_CONFIG_PATH", json.loads(stdout)["fatal"]["code"])


if __name__ == "__main__":
    unittest.main()
