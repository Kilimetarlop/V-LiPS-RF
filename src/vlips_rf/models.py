"""Serializable validation result models."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


LEVELS = ("L0", "L1", "L2", "L3", "L4")
LEVEL_INDEX = {name: index for index, name in enumerate(LEVELS)}


def normalize_level(value: str) -> str:
    normalized = str(value).strip().upper()
    if normalized not in LEVEL_INDEX:
        raise ValueError("level must be one of L0, L1, L2, L3, or L4")
    return normalized


@dataclass(frozen=True)
class ValidationIssue:
    """A stable, machine-readable validation finding.

    ``level`` is the first evidence level blocked by the finding.  A finding
    therefore becomes an error only when the caller requires that level (or a
    higher one); otherwise it remains a warning about a stronger claim.
    """

    code: str
    level: str
    message: str
    location: Optional[str] = None
    row: Optional[int] = None
    details: Dict[str, Any] = field(default_factory=dict)
    remediation: Optional[str] = None
    status: str = "fail"

    def to_dict(self, required_level: str, explain: bool = False) -> Dict[str, Any]:
        required_level = normalize_level(required_level)
        severity = (
            "error"
            if LEVEL_INDEX[required_level] >= LEVEL_INDEX[self.level]
            else "warning"
        )
        result: Dict[str, Any] = {
            "code": self.code,
            "severity": severity,
            "status": self.status,
            "level": self.level,
            "message": self.message,
        }
        if self.location is not None:
            result["location"] = self.location
        if self.row is not None:
            result["row"] = self.row
        if self.details:
            result["details"] = self.details
        if explain and self.remediation:
            result["remediation"] = self.remediation
        return result


@dataclass
class ValidationReport:
    artifact: str
    required_level: str
    highest_provable_level: Optional[str]
    accepted: bool
    declared_level: str
    checks: Dict[str, Dict[str, Any]]
    issues: List[ValidationIssue]
    statistics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, explain: bool = False) -> Dict[str, Any]:
        return {
            "schema_version": "1.0",
            "artifact": self.artifact,
            "required_level": self.required_level,
            "highest_provable_level": self.highest_provable_level,
            "accepted": self.accepted,
            "declared_level": self.declared_level,
            "checks": self.checks,
            "statistics": self.statistics,
            "issues": [
                issue.to_dict(self.required_level, explain=explain)
                for issue in self.issues
            ],
        }
