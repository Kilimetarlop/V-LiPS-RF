from __future__ import annotations

import contextlib
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vlips_rf import select_candidate  # noqa: E402
from vlips_rf.cli import main as cli_main  # noqa: E402
from vlips_rf.errors import ArtifactError  # noqa: E402
from vlips_rf.selection import CANDIDATE_COLUMNS  # noqa: E402


def candidate(candidate_id: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "candidate_id": candidate_id,
        "eligible": "true",
        "identity_count": 10,
        "acquisition_count": 20,
        "condition_count": 3,
        "role_imbalance": 0.1,
        "legal_signal_count": 100,
        "transfer_bytes": 1000,
    }
    row.update(overrides)
    return row


class SelectionContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_candidates(
        self,
        rows: list[dict[str, object]],
        extra_columns: tuple[str, ...] = (),
    ) -> Path:
        path = self.root / "candidates.csv"
        fields = list(CANDIDATE_COLUMNS) + list(extra_columns)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_outcome_bearing_column_is_rejected_before_selection(self) -> None:
        row = candidate("safe")
        row["test_accuracy"] = 0.99
        path = self.write_candidates([row], extra_columns=("test_accuracy",))

        with self.assertRaises(ArtifactError) as caught:
            select_candidate(path)
        self.assertEqual("E_OUTCOME_COLUMN_FORBIDDEN", caught.exception.code)

    def test_ineligible_candidate_is_filtered_even_when_structurally_superior(self) -> None:
        path = self.write_candidates(
            [
                candidate("unsafe", eligible="false", identity_count=999),
                candidate("safe", identity_count=5),
            ]
        )
        result = select_candidate(path)

        self.assertEqual("safe", result.selected_candidate_id)
        self.assertEqual(2, result.candidate_count)
        self.assertEqual(1, result.eligible_count)
        self.assertEqual(["safe"], result.ranking)

    def test_frozen_lexicographic_policy_orders_structural_fields(self) -> None:
        path = self.write_candidates(
            [
                candidate("low-identities", identity_count=9, acquisition_count=999),
                candidate("low-acquisitions", acquisition_count=19, condition_count=999),
                candidate("low-conditions", condition_count=2, role_imbalance=0),
                candidate("high-imbalance", role_imbalance=0.2, legal_signal_count=999),
                candidate("low-legal", legal_signal_count=99, transfer_bytes=0),
                candidate("high-transfer", transfer_bytes=1001),
                candidate("winner"),
            ]
        )
        result = select_candidate(path)

        self.assertEqual("winner", result.selected_candidate_id)
        self.assertEqual(
            [
                "winner",
                "high-transfer",
                "low-legal",
                "high-imbalance",
                "low-conditions",
                "low-acquisitions",
                "low-identities",
            ],
            result.ranking,
        )

    def test_exact_structural_tie_is_broken_by_candidate_id(self) -> None:
        path = self.write_candidates([candidate("zeta"), candidate("alpha")])
        result = select_candidate(path)
        self.assertEqual("alpha", result.selected_candidate_id)
        self.assertEqual(["alpha", "zeta"], result.ranking)

    def test_cli_select_json_and_exit_codes(self) -> None:
        path = self.write_candidates([candidate("chosen")])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli_main(["select", str(path), "--format", "json"])
        self.assertEqual(0, code)
        self.assertEqual("chosen", json.loads(stdout.getvalue())["selected_candidate_id"])

        row = candidate("blocked")
        row["validation_loss"] = 0.01
        path = self.write_candidates([row], extra_columns=("validation_loss",))
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli_main(["select", str(path), "--format", "json"])
        self.assertEqual(2, code)
        self.assertEqual(
            "E_OUTCOME_COLUMN_FORBIDDEN",
            json.loads(stdout.getvalue())["fatal"]["code"],
        )


if __name__ == "__main__":
    unittest.main()
