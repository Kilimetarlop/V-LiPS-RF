"""Canonical V-LiPS-RF artifact schema."""

import json
from pathlib import Path
from typing import Any, Dict, Optional, TextIO

from .errors import ArtifactError


SEGMENT_COLUMNS = (
    "segment_id",
    "physical_emitter_id",
    "acquisition_id",
    "source_file_id",
    "sample_start",
    "sample_end",
    "model_version",
    "role",
    "usage",
    "evidence_level",
)

TRANSITION_COLUMNS = (
    "transition_id",
    "from_role",
    "to_role",
    "action",
    "from_model_version",
    "to_model_version",
    "fresh_relative_to_previous_versions",
)


def artifact_schema() -> Dict[str, Any]:
    """Return the complete, versioned artifact schema as plain Python data."""

    return {
        "schema_version": "1.0",
        "artifact_type": "vlips-rf",
        "levels": {
            "L0": "Cross-role interval and source-file isolation.",
            "L1": "L0 plus acquisition/group isolation.",
            "L2": "L1 plus physical-identity isolation.",
            "L3": "L2 plus full pipeline and model-version isolation.",
            "L4": "L3 plus a fresh-query-compliant U-S-K transition.",
        },
        "configuration": {
            "file": "vlips.yaml",
            "encoding": "UTF-8",
            "syntax": "JSON (which is also valid YAML 1.2)",
            "required": ["schema_version", "artifact_type", "declared_level"],
            "declared_level": {"enum": ["L0", "L1", "L2", "L3", "L4"]},
            "files": {
                "segments": "segments.csv",
                "pipeline_dependencies": "pipeline_dependencies.json",
                "query_transitions": "query_transitions.csv",
            },
        },
        "segments": {
            "file": "segments.csv",
            "format": "CSV with a header row",
            "columns": list(SEGMENT_COLUMNS),
            "interval_semantics": "Half-open [sample_start, sample_end).",
            "evidence_level": {
                "accepted": [
                    "confirmed",
                    "release_sequence",
                    "conservative_bundle",
                    "resolved",
                    "verified",
                    "complete",
                    "L0",
                    "L1",
                    "L2",
                    "L3",
                    "L4",
                    "unresolved",
                ],
                "note": (
                    "unresolved evidence caps the highest provable level at L0; "
                    "an explicit L0-L4 value caps it at that level."
                ),
            },
        },
        "pipeline_dependencies": {
            "file": "pipeline_dependencies.json",
            "required_for": "L3",
            "shape": {
                "nodes": [
                    {
                        "id": "string",
                        "role": "string",
                        "usage": "string",
                        "model_version": "string",
                    }
                ],
                "edges": [{"from": "node id", "to": "node id"}],
            },
        },
        "query_transitions": {
            "file": "query_transitions.csv",
            "required_for": "L4",
            "columns": list(TRANSITION_COLUMNS),
        },
    }


def export_schema(
    destination: Optional[Path] = None,
    *,
    stream: Optional[TextIO] = None,
) -> Dict[str, Any]:
    """Write the schema to a file or stream and return it.

    With neither argument the function simply returns the schema.  The CLI
    writes that returned value to standard output.
    """

    schema = artifact_schema()
    rendered = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    if destination is not None and stream is not None:
        raise ArtifactError(
            "E_SCHEMA_DESTINATION",
            "choose either a destination path or a stream, not both",
        )
    if destination is not None:
        try:
            Path(destination).write_text(rendered, encoding="utf-8")
        except OSError as exc:
            raise ArtifactError(
                "E_SCHEMA_WRITE",
                "could not write the schema",
                path=str(destination),
                details={"reason": str(exc)},
            ) from exc
    elif stream is not None:
        stream.write(rendered)
    return schema
