"""Deterministic, outcome-blind candidate selection.

Selection reads only predeclared legality, coverage, balance, and transfer-cost
fields.  Outcome-bearing columns are rejected before any candidate is parsed.
"""

import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Set, Tuple

from .errors import ArtifactError


CANDIDATE_COLUMNS = (
    "candidate_id",
    "eligible",
    "identity_count",
    "acquisition_count",
    "condition_count",
    "role_imbalance",
    "legal_signal_count",
    "transfer_bytes",
)

FORBIDDEN_OUTCOME_TOKENS = {
    "outcome",
    "label",
    "labels",
    "prediction",
    "predictions",
    "accuracy",
    "auroc",
    "auc",
    "ap",
    "loss",
    "losses",
    "score",
    "scores",
    "metric",
    "metrics",
    "f1",
    "precision",
    "recall",
    "eer",
}

TRUE_VALUES = {"1", "true", "yes", "y", "eligible"}
FALSE_VALUES = {"0", "false", "no", "n", "ineligible"}


@dataclass(frozen=True)
class SelectionResult:
    source: str
    selected_candidate_id: str
    selected: Dict[str, Any]
    candidate_count: int
    eligible_count: int
    ranking: List[str]
    policy: Tuple[str, ...] = (
        "eligible=true",
        "maximize identity_count",
        "maximize acquisition_count",
        "maximize condition_count",
        "minimize role_imbalance",
        "maximize legal_signal_count",
        "minimize transfer_bytes",
        "lexicographic candidate_id tie-break",
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": "1.0",
            "source": self.source,
            "selected_candidate_id": self.selected_candidate_id,
            "selected": self.selected,
            "candidate_count": self.candidate_count,
            "eligible_count": self.eligible_count,
            "ranking": self.ranking,
            "policy": list(self.policy),
        }


def _tokens(header: str) -> Set[str]:
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", header).casefold()
    return {token for token in re.split(r"[^a-z0-9]+", normalized) if token}


def _integer(value: str, field: str, row: int) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise ArtifactError(
            "E_CANDIDATE_NUMBER",
            f"{field} must be an integer",
            details={"row": row, "field": field, "value": value},
        ) from exc
    if number < 0:
        raise ArtifactError(
            "E_CANDIDATE_RANGE",
            f"{field} must be non-negative",
            details={"row": row, "field": field, "value": value},
        )
    return number


def _imbalance(value: str, row: int) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise ArtifactError(
            "E_CANDIDATE_NUMBER",
            "role_imbalance must be numeric",
            details={"row": row, "field": "role_imbalance", "value": value},
        ) from exc
    if not math.isfinite(number) or number < 0:
        raise ArtifactError(
            "E_CANDIDATE_RANGE",
            "role_imbalance must be finite and non-negative",
            details={"row": row, "field": "role_imbalance", "value": value},
        )
    return number


def _parse_eligible(value: str, row: int) -> bool:
    normalized = value.strip().casefold()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ArtifactError(
        "E_CANDIDATE_ELIGIBLE",
        "eligible must be a recognized boolean",
        details={"row": row, "value": value},
    )


def _rank_key(candidate: Mapping[str, Any]) -> Tuple[Any, ...]:
    return (
        -candidate["identity_count"],
        -candidate["acquisition_count"],
        -candidate["condition_count"],
        candidate["role_imbalance"],
        -candidate["legal_signal_count"],
        candidate["transfer_bytes"],
        candidate["candidate_id"],
    )


def select_candidate(path: Path) -> SelectionResult:
    """Select one eligible candidate by the frozen outcome-blind ordering."""

    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ArtifactError(
            "E_CANDIDATES_MISSING", "candidate CSV does not exist", path=str(source)
        )
    try:
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = list(reader.fieldnames or [])
            forbidden = sorted(
                header
                for header in headers
                if _tokens(header) & FORBIDDEN_OUTCOME_TOKENS
            )
            if forbidden:
                raise ArtifactError(
                    "E_OUTCOME_COLUMN_FORBIDDEN",
                    "outcome-bearing columns are forbidden in candidate selection",
                    path=str(source),
                    details={"columns": forbidden},
                )
            missing = [column for column in CANDIDATE_COLUMNS if column not in headers]
            if missing:
                raise ArtifactError(
                    "E_CANDIDATE_HEADER",
                    "candidate CSV is missing required columns",
                    path=str(source),
                    details={"missing": missing},
                )
            rows = list(reader)
    except ArtifactError:
        raise
    except UnicodeError as exc:
        raise ArtifactError(
            "E_CANDIDATE_ENCODING", "candidate CSV must be UTF-8", path=str(source)
        ) from exc
    except (OSError, csv.Error) as exc:
        raise ArtifactError(
            "E_CANDIDATE_READ",
            "could not read candidate CSV",
            path=str(source),
            details={"reason": str(exc)},
        ) from exc

    candidates: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for row_number, raw in enumerate(rows, start=2):
        row = {key: (value or "").strip() for key, value in raw.items() if key}
        missing_values = [column for column in CANDIDATE_COLUMNS if not row.get(column, "")]
        if missing_values:
            raise ArtifactError(
                "E_CANDIDATE_FIELDS",
                "candidate has missing required values",
                path=str(source),
                details={"row": row_number, "missing": missing_values},
            )
        candidate_id = row["candidate_id"]
        if candidate_id in seen:
            raise ArtifactError(
                "E_CANDIDATE_DUPLICATE",
                "candidate_id is duplicated",
                path=str(source),
                details={"row": row_number, "candidate_id": candidate_id},
            )
        seen.add(candidate_id)
        try:
            eligible = _parse_eligible(row["eligible"], row_number)
            candidate: Dict[str, Any] = {
                "candidate_id": candidate_id,
                "eligible": eligible,
                "identity_count": _integer(row["identity_count"], "identity_count", row_number),
                "acquisition_count": _integer(row["acquisition_count"], "acquisition_count", row_number),
                "condition_count": _integer(row["condition_count"], "condition_count", row_number),
                "role_imbalance": _imbalance(row["role_imbalance"], row_number),
                "legal_signal_count": _integer(row["legal_signal_count"], "legal_signal_count", row_number),
                "transfer_bytes": _integer(row["transfer_bytes"], "transfer_bytes", row_number),
            }
        except ArtifactError as exc:
            if exc.path is None:
                exc.path = str(source)
            raise
        candidates.append(candidate)
    if not candidates:
        raise ArtifactError(
            "E_CANDIDATES_EMPTY", "candidate CSV contains no candidates", path=str(source)
        )
    eligible_candidates = [candidate for candidate in candidates if candidate["eligible"]]
    if not eligible_candidates:
        raise ArtifactError(
            "E_NO_ELIGIBLE_CANDIDATE",
            "candidate CSV contains no eligible candidate",
            path=str(source),
        )
    ranked = sorted(eligible_candidates, key=_rank_key)
    selected = ranked[0]
    return SelectionResult(
        source=str(source),
        selected_candidate_id=selected["candidate_id"],
        selected=dict(selected),
        candidate_count=len(candidates),
        eligible_count=len(eligible_candidates),
        ranking=[candidate["candidate_id"] for candidate in ranked],
    )
