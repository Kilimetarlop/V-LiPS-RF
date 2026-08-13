"""Stable exceptions exposed by the artifact and CLI layers."""

from typing import Any, Dict, Optional


class ArtifactError(Exception):
    """A fatal artifact, configuration, or I/O error.

    Validation findings are represented by :class:`ValidationIssue`; this
    exception is reserved for conditions that prevent validation from running.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        path: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.path is not None:
            result["path"] = self.path
        if self.details:
            result["details"] = self.details
        return result

