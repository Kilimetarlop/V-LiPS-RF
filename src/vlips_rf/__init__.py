"""Public API for V-LiPS-RF.

The package intentionally depends only on the Python standard library.  Its
artifact format is file based, deterministic, and suitable for both command
line use and embedding in experiment tooling.
"""

from .artifact import create_demo, initialize_artifact, inspect_artifact
from .schema import artifact_schema, export_schema
from .validation import validate_artifact
from .models import ValidationIssue, ValidationReport
from .selection import SelectionResult, select_candidate

__all__ = [
    "ValidationIssue",
    "ValidationReport",
    "SelectionResult",
    "artifact_schema",
    "create_demo",
    "export_schema",
    "initialize_artifact",
    "inspect_artifact",
    "select_candidate",
    "validate_artifact",
]

__version__ = "0.1.0"
