"""Artifact creation, configuration, and inspection helpers."""

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

from .errors import ArtifactError
from .models import LEVEL_INDEX, LEVELS, normalize_level
from .schema import SEGMENT_COLUMNS, TRANSITION_COLUMNS


DEFAULT_FILES = {
    "segments": "segments.csv",
    "pipeline_dependencies": "pipeline_dependencies.json",
    "query_transitions": "query_transitions.csv",
}


def _safe_artifact_file(root: Path, value: str, key: str) -> Path:
    raw = Path(value)
    if raw.is_absolute():
        raise ArtifactError(
            "E_CONFIG_PATH",
            "artifact file paths must be relative",
            path=str(root / "vlips.yaml"),
            details={"key": key, "value": value},
        )
    root_resolved = root.resolve()
    candidate = (root / raw).resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ArtifactError(
            "E_CONFIG_PATH",
            "artifact file path escapes the artifact root",
            path=str(root / "vlips.yaml"),
            details={"key": key, "value": value},
        )
    return candidate


def load_config(path: Path) -> Tuple[Path, Dict[str, Any], Dict[str, Path]]:
    root = Path(path).expanduser().resolve()
    config_path = root / "vlips.yaml"
    if not root.is_dir():
        raise ArtifactError(
            "E_ARTIFACT_DIRECTORY",
            "artifact path is not a directory",
            path=str(root),
        )
    if not config_path.is_file():
        raise ArtifactError(
            "E_CONFIG_MISSING",
            "vlips.yaml is required at the artifact root",
            path=str(config_path),
        )
    try:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except UnicodeError as exc:
        raise ArtifactError(
            "E_CONFIG_ENCODING",
            "vlips.yaml must be UTF-8",
            path=str(config_path),
        ) from exc
    except json.JSONDecodeError as exc:
        raise ArtifactError(
            "E_CONFIG_SYNTAX",
            "vlips.yaml must use JSON syntax (a valid YAML 1.2 subset)",
            path=str(config_path),
            details={"line": exc.lineno, "column": exc.colno},
        ) from exc
    except OSError as exc:
        raise ArtifactError(
            "E_CONFIG_READ",
            "could not read vlips.yaml",
            path=str(config_path),
            details={"reason": str(exc)},
        ) from exc
    if not isinstance(config, dict):
        raise ArtifactError(
            "E_CONFIG_SHAPE",
            "vlips.yaml must contain a JSON object",
            path=str(config_path),
        )
    if config.get("artifact_type") != "vlips-rf":
        raise ArtifactError(
            "E_ARTIFACT_TYPE",
            "artifact_type must be 'vlips-rf'",
            path=str(config_path),
        )
    if str(config.get("schema_version", "")) != "1.0":
        raise ArtifactError(
            "E_SCHEMA_VERSION",
            "schema_version must be '1.0'",
            path=str(config_path),
        )
    try:
        config["declared_level"] = normalize_level(config.get("declared_level", ""))
    except ValueError as exc:
        raise ArtifactError(
            "E_DECLARED_LEVEL",
            str(exc),
            path=str(config_path),
        ) from exc

    configured_files = config.get("files", {})
    if configured_files is None:
        configured_files = {}
    if not isinstance(configured_files, dict):
        raise ArtifactError(
            "E_CONFIG_FILES",
            "files must be a JSON object",
            path=str(config_path),
        )
    files: Dict[str, Path] = {}
    for key, default in DEFAULT_FILES.items():
        value = configured_files.get(key, default)
        if not isinstance(value, str) or not value.strip():
            raise ArtifactError(
                "E_CONFIG_FILE_VALUE",
                "configured artifact file must be a non-empty string",
                path=str(config_path),
                details={"key": key},
            )
        files[key] = _safe_artifact_file(root, value, key)
    return root, config, files


def _prepare_target(path: Path) -> Path:
    target = Path(path).expanduser().resolve()
    if target.exists() and not target.is_dir():
        raise ArtifactError(
            "E_TARGET_TYPE", "target exists and is not a directory", path=str(target)
        )
    if target.is_dir():
        try:
            if any(target.iterdir()):
                raise ArtifactError(
                    "E_TARGET_NOT_EMPTY",
                    "target directory must be empty",
                    path=str(target),
                )
        except OSError as exc:
            raise ArtifactError(
                "E_TARGET_READ",
                "could not inspect target directory",
                path=str(target),
                details={"reason": str(exc)},
            ) from exc
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ArtifactError(
            "E_TARGET_CREATE",
            "could not create target directory",
            path=str(target),
            details={"reason": str(exc)},
        ) from exc
    return target


def _write_csv(path: Path, columns: Tuple[str, ...], rows: List[Mapping[str, Any]]) -> None:
    try:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    except OSError as exc:
        raise ArtifactError(
            "E_ARTIFACT_WRITE",
            "could not write artifact file",
            path=str(path),
            details={"reason": str(exc)},
        ) from exc


def initialize_artifact(path: Path, level: str = "L0") -> Path:
    """Create an empty V-LiPS-RF artifact scaffold."""

    try:
        level = normalize_level(level)
    except ValueError as exc:
        raise ArtifactError("E_DECLARED_LEVEL", str(exc)) from exc
    target = _prepare_target(Path(path))
    config = {
        "schema_version": "1.0",
        "artifact_type": "vlips-rf",
        "declared_level": level,
        "files": dict(DEFAULT_FILES),
    }
    try:
        (target / "vlips.yaml").write_text(
            json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        raise ArtifactError(
            "E_ARTIFACT_WRITE",
            "could not write artifact configuration",
            path=str(target / "vlips.yaml"),
            details={"reason": str(exc)},
        ) from exc
    _write_csv(target / "segments.csv", SEGMENT_COLUMNS, [])
    if LEVEL_INDEX[level] >= LEVEL_INDEX["L3"]:
        try:
            (target / "pipeline_dependencies.json").write_text(
                json.dumps(
                    {"schema_version": "1.0", "nodes": [], "edges": []},
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise ArtifactError(
                "E_ARTIFACT_WRITE",
                "could not write pipeline dependency scaffold",
                path=str(target / "pipeline_dependencies.json"),
                details={"reason": str(exc)},
            ) from exc
    if level == "L4":
        _write_csv(target / "query_transitions.csv", TRANSITION_COLUMNS, [])
    return target


def create_demo(path: Path) -> Path:
    """Create a small, valid L4 artifact that can be validated immediately."""

    target = initialize_artifact(path, "L4")
    rows = [
        {
            "segment_id": "train-segment-001",
            "physical_emitter_id": "emitter-train-01",
            "acquisition_id": "acquisition-train-01",
            "source_file_id": "source-train-01",
            "sample_start": 0,
            "sample_end": 4096,
            "model_version": "model-v1",
            "role": "train",
            "usage": "fit",
            "evidence_level": "resolved",
        },
        {
            "segment_id": "validation-segment-001",
            "physical_emitter_id": "emitter-validation-01",
            "acquisition_id": "acquisition-validation-01",
            "source_file_id": "source-validation-01",
            "sample_start": 0,
            "sample_end": 4096,
            "model_version": "model-v1",
            "role": "validation",
            "usage": "select",
            "evidence_level": "resolved",
        },
        {
            "segment_id": "test-segment-001",
            "physical_emitter_id": "emitter-test-01",
            "acquisition_id": "acquisition-test-01",
            "source_file_id": "source-test-01",
            "sample_start": 0,
            "sample_end": 4096,
            "model_version": "model-v1",
            "role": "test",
            "usage": "evaluate",
            "evidence_level": "resolved",
        },
    ]
    _write_csv(target / "segments.csv", SEGMENT_COLUMNS, rows)
    pipeline = {
        "schema_version": "1.0",
        "nodes": [
            {
                "id": "fit-model-v1",
                "role": "train",
                "usage": "fit",
                "model_version": "model-v1",
            },
            {
                "id": "select-model-v1",
                "role": "validation",
                "usage": "select",
                "model_version": "model-v1",
            },
            {
                "id": "evaluate-model-v1",
                "role": "test",
                "usage": "evaluate",
                "model_version": "model-v1",
            },
        ],
        "edges": [
            {"from": "fit-model-v1", "to": "select-model-v1"},
            {"from": "select-model-v1", "to": "evaluate-model-v1"},
        ],
    }
    try:
        (target / "pipeline_dependencies.json").write_text(
            json.dumps(pipeline, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        raise ArtifactError(
            "E_ARTIFACT_WRITE",
            "could not write demo pipeline",
            path=str(target / "pipeline_dependencies.json"),
            details={"reason": str(exc)},
        ) from exc
    _write_csv(
        target / "query_transitions.csv",
        TRANSITION_COLUMNS,
        [
            {
                "transition_id": "fresh-query-transition-001",
                "from_role": "U",
                "to_role": "K",
                "action": "external_confirmation",
                "from_model_version": "model-v1",
                "to_model_version": "model-v2",
                "fresh_relative_to_previous_versions": "true",
            }
        ],
    )
    return target


def inspect_artifact(path: Path) -> Dict[str, Any]:
    """Return a non-mutating summary of an artifact and its evidence files."""

    root, config, files = load_config(Path(path))
    file_summary: Dict[str, Any] = {}
    for key, file_path in files.items():
        entry: Dict[str, Any] = {
            "path": str(file_path.relative_to(root)),
            "exists": file_path.is_file(),
        }
        if file_path.is_file():
            try:
                entry["bytes"] = file_path.stat().st_size
            except OSError:
                entry["bytes"] = None
        file_summary[key] = entry

    segment_count = None
    segments_path = files["segments"]
    if segments_path.is_file():
        try:
            with segments_path.open("r", encoding="utf-8-sig", newline="") as handle:
                segment_count = sum(1 for _ in csv.DictReader(handle))
        except (OSError, UnicodeError, csv.Error):
            segment_count = None
    return {
        "schema_version": "1.0",
        "artifact": str(root),
        "artifact_type": config["artifact_type"],
        "declared_level": config["declared_level"],
        "segment_count": segment_count,
        "files": file_summary,
    }
