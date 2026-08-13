"""Layered, outcome-blind validation for V-LiPS-RF artifacts."""

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from .artifact import load_config
from .errors import ArtifactError
from .models import LEVEL_INDEX, LEVELS, ValidationIssue, ValidationReport, normalize_level
from .schema import SEGMENT_COLUMNS, TRANSITION_COLUMNS


RESOLVED_EVIDENCE = {
    "confirmed",
    "release_sequence",
    "conservative_bundle",
    "resolved",
    "verified",
    "complete",
}
UNRESOLVED_EVIDENCE = {"", "unresolved", "unknown", "missing", "pending"}
HELD_OUT_ROLES = {
    "u",
    "unknown",
    "test",
    "testing",
    "holdout",
    "heldout",
    "evaluation",
}
UPDATE_USAGES = {
    "fit",
    "train",
    "tune",
    "select",
    "calibrate",
    "update",
    "write",
    "optimize",
}


def _semantic_role(value: str) -> str:
    role = str(value).strip().casefold()
    if role in {"k", "known", "train", "training", "enrollment", "enrolled"}:
        return "k"
    if role in {"s", "validation", "calibration", "selection"}:
        return "s"
    if role in HELD_OUT_ROLES:
        return "u"
    return role


def _semantic_usage(value: str) -> str:
    usage = str(value).strip().casefold()
    if usage in {"enrollment", "fit", "train", "training"}:
        return "fit"
    if usage in {"calibration", "calibrate", "select", "selection", "tune"}:
        return "prepare"
    if usage in {"final_query", "evaluate", "evaluation", "inference"}:
        return "evaluate"
    if usage in {"adapt", "adaptation", "update", "write", "optimize"}:
        return "update"
    return usage


def _issue(
    code: str,
    level: str,
    message: str,
    *,
    location: Optional[str] = None,
    row: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    remediation: Optional[str] = None,
    status: str = "fail",
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        level=level,
        message=message,
        location=location,
        row=row,
        details=details or {},
        remediation=remediation,
        status=status,
    )


def _read_csv(path: Path, missing_code: str, label: str) -> Tuple[List[str], List[Dict[str, str]]]:
    if not path.is_file():
        return [], []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = list(reader.fieldnames or [])
            rows = []
            for raw in reader:
                rows.append({key: (value or "").strip() for key, value in raw.items() if key})
            return headers, rows
    except UnicodeError as exc:
        raise ArtifactError(
            "E_CSV_ENCODING", f"{label} must be UTF-8", path=str(path)
        ) from exc
    except (OSError, csv.Error) as exc:
        raise ArtifactError(
            "E_CSV_READ",
            f"could not read {label}",
            path=str(path),
            details={"reason": str(exc)},
        ) from exc


def _roles_by(rows: Iterable[Mapping[str, Any]], key: str) -> Dict[str, Set[str]]:
    result: DefaultDict[str, Set[str]] = defaultdict(set)
    for row in rows:
        entity = str(row.get(key, "")).strip()
        role = _semantic_role(str(row.get("role", "")))
        if entity and role:
            result[entity].add(role)
    return dict(result)


def _cross_role_findings(
    rows: List[Dict[str, Any]],
    key: str,
    level: str,
    code: str,
    label: str,
    location: str,
) -> List[ValidationIssue]:
    findings = []
    for entity, roles in sorted(_roles_by(rows, key).items()):
        if len(roles) > 1:
            findings.append(
                _issue(
                    code,
                    level,
                    f"{label} is assigned to more than one role",
                    location=location,
                    details={key: entity, "roles": sorted(roles)},
                    remediation=f"assign each {label} to exactly one partition role",
                )
            )
    return findings


def _has_cycle(adjacency: Dict[str, Set[str]]) -> bool:
    visiting: Set[str] = set()
    visited: Set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for target in adjacency.get(node, set()):
            if visit(target):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in adjacency)


def _reachable(adjacency: Dict[str, Set[str]], source: str) -> Set[str]:
    found: Set[str] = set()
    pending = list(adjacency.get(source, set()))
    while pending:
        node = pending.pop()
        if node in found:
            continue
        found.add(node)
        pending.extend(adjacency.get(node, set()) - found)
    return found


def _validate_pipeline(
    path: Path,
    required_bindings: Set[Tuple[str, str, str]],
) -> Tuple[List[ValidationIssue], Dict[str, int]]:
    findings: List[ValidationIssue] = []
    stats = {"pipeline_nodes": 0, "pipeline_edges": 0}
    if not path.is_file():
        findings.append(
            _issue(
                "E_PIPELINE_DEPENDENCIES_MISSING",
                "L3",
                "pipeline dependency evidence is required for L3",
                location=str(path),
                remediation="add pipeline_dependencies.json or lower the required level",
                status="not_checkable",
            )
        )
        return findings, stats
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except UnicodeError as exc:
        raise ArtifactError("E_PIPELINE_ENCODING", "pipeline JSON must be UTF-8", path=str(path)) from exc
    except json.JSONDecodeError as exc:
        findings.append(
            _issue(
                "E_PIPELINE_SYNTAX",
                "L3",
                "pipeline dependency file is not valid JSON",
                location=str(path),
                details={"line": exc.lineno, "column": exc.colno},
                remediation="export a JSON object with nodes and edges arrays",
            )
        )
        return findings, stats
    except OSError as exc:
        raise ArtifactError(
            "E_PIPELINE_READ", "could not read pipeline dependencies", path=str(path),
            details={"reason": str(exc)},
        ) from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("nodes"), list) or not isinstance(payload.get("edges"), list):
        findings.append(
            _issue(
                "E_PIPELINE_SHAPE",
                "L3",
                "pipeline dependencies must contain nodes and edges arrays",
                location=str(path),
                remediation="follow the shape emitted by 'vlips schema export'",
            )
        )
        return findings, stats

    nodes: Dict[str, Dict[str, str]] = {}
    for index, raw in enumerate(payload["nodes"], start=1):
        if not isinstance(raw, dict):
            findings.append(
                _issue(
                    "E_PIPELINE_NODE",
                    "L3",
                    "pipeline node must be an object",
                    location=str(path),
                    row=index,
                )
            )
            continue
        node = {key: str(raw.get(key, "")).strip() for key in ("id", "role", "usage", "model_version")}
        missing = [key for key, value in node.items() if not value]
        if missing:
            findings.append(
                _issue(
                    "E_PIPELINE_NODE_FIELDS",
                    "L3",
                    "pipeline node has missing required fields",
                    location=str(path),
                    row=index,
                    details={"missing": missing},
                )
            )
            continue
        if node["id"] in nodes:
            findings.append(
                _issue(
                    "E_PIPELINE_NODE_DUPLICATE",
                    "L3",
                    "pipeline node id is duplicated",
                    location=str(path),
                    row=index,
                    details={"id": node["id"]},
                )
            )
            continue
        nodes[node["id"]] = node
    stats["pipeline_nodes"] = len(nodes)
    if not nodes:
        findings.append(
            _issue(
                "E_PIPELINE_EMPTY",
                "L3",
                "pipeline dependency graph has no valid nodes",
                location=str(path),
                remediation="record the fit, selection, and evaluation stages as nodes",
            )
        )

    declared_bindings = {
        (
            _semantic_role(node["role"]),
            _semantic_usage(node["usage"]),
            node["model_version"],
        )
        for node in nodes.values()
    }
    missing_bindings = sorted(required_bindings - declared_bindings)
    if missing_bindings:
        findings.append(
            _issue(
                "E_PIPELINE_STAGE_COVERAGE",
                "L3",
                "pipeline graph does not cover every stage declared by the segment manifest",
                location=str(path),
                details={
                    "missing": [
                        {"role": role, "usage": usage, "model_version": version}
                        for role, usage, version in missing_bindings
                    ]
                },
                remediation="add one graph node for every declared role, use, and model-version binding",
                status="not_checkable",
            )
        )

    adjacency: Dict[str, Set[str]] = {node_id: set() for node_id in nodes}
    valid_edges = 0
    for index, raw in enumerate(payload["edges"], start=1):
        if not isinstance(raw, dict):
            findings.append(
                _issue(
                    "E_PIPELINE_EDGE",
                    "L3",
                    "pipeline edge must be an object",
                    location=str(path),
                    row=index,
                )
            )
            continue
        source = str(raw.get("from", "")).strip()
        target = str(raw.get("to", "")).strip()
        if source not in nodes or target not in nodes:
            findings.append(
                _issue(
                    "E_PIPELINE_EDGE_REFERENCE",
                    "L3",
                    "pipeline edge references an unknown node",
                    location=str(path),
                    row=index,
                    details={"from": source, "to": target},
                    remediation="declare both edge endpoints in the nodes array",
                )
            )
            continue
        adjacency[source].add(target)
        valid_edges += 1
    stats["pipeline_edges"] = valid_edges
    if len(required_bindings) > 1 and valid_edges == 0:
        findings.append(
            _issue(
                "E_PIPELINE_EDGES_EMPTY",
                "L3",
                "a multi-stage pipeline requires declared dependency edges",
                location=str(path),
                remediation="declare the directed dependencies between the recorded pipeline stages",
                status="not_checkable",
            )
        )
    if _has_cycle(adjacency):
        findings.append(
            _issue(
                "E_PIPELINE_CYCLE",
                "L3",
                "pipeline dependency graph contains a directed cycle",
                location=str(path),
                remediation="record each post-query update as a new model version and an acyclic stage",
            )
        )

    seen_backwrites: Set[Tuple[str, str]] = set()
    for source_id, source in nodes.items():
        if _semantic_role(source["role"]) != "u":
            continue
        for target_id in _reachable(adjacency, source_id):
            target = nodes[target_id]
            if _semantic_usage(target["usage"]) not in {"fit", "prepare", "update"}:
                continue
            if target["model_version"] == source["model_version"]:
                pair = (source_id, target_id)
                if pair in seen_backwrites:
                    continue
                seen_backwrites.add(pair)
                findings.append(
                    _issue(
                        "E_PIPELINE_BACKWRITE_SAME_VERSION",
                        "L3",
                        "held-out evidence reaches an update stage without a new model version",
                        location=str(path),
                        details={
                            "from": source_id,
                            "to": target_id,
                            "model_version": source["model_version"],
                        },
                        remediation="bind the update and all downstream evaluations to a new model version",
                    )
                )
    return findings, stats


def _validate_transitions(path: Path) -> Tuple[List[ValidationIssue], Dict[str, int]]:
    findings: List[ValidationIssue] = []
    stats = {"query_transitions": 0}
    if not path.is_file():
        findings.append(
            _issue(
                "E_QUERY_TRANSITIONS_MISSING",
                "L4",
                "query transition evidence is required for L4",
                location=str(path),
                remediation="add query_transitions.csv or lower the required level",
                status="not_checkable",
            )
        )
        return findings, stats
    headers, rows = _read_csv(path, "E_QUERY_TRANSITIONS_MISSING", "query transitions")
    missing = [column for column in TRANSITION_COLUMNS if column not in headers]
    if missing:
        findings.append(
            _issue(
                "E_QUERY_TRANSITION_HEADER",
                "L4",
                "query transition CSV is missing required columns",
                location=str(path),
                details={"missing": missing},
                remediation="use the header emitted by 'vlips init ... --level L4'",
            )
        )
        return findings, stats
    stats["query_transitions"] = len(rows)
    if not rows:
        findings.append(
            _issue(
                "E_QUERY_TRANSITIONS_EMPTY",
                "L4",
                "at least one fresh-query transition is required for L4",
                location=str(path),
                remediation="record a U/S-to-K transition that binds a fresh query to a new version",
                status="not_checkable",
            )
        )
    seen: Set[str] = set()
    for index, row in enumerate(rows, start=2):
        missing_values = [column for column in TRANSITION_COLUMNS if not row.get(column, "").strip()]
        if missing_values:
            findings.append(
                _issue(
                    "E_QUERY_TRANSITION_FIELDS",
                    "L4",
                    "query transition has missing required values",
                    location=str(path),
                    row=index,
                    details={"missing": missing_values},
                )
            )
            continue
        transition_id = row["transition_id"]
        if transition_id in seen:
            findings.append(
                _issue(
                    "E_QUERY_TRANSITION_DUPLICATE",
                    "L4",
                    "query transition id is duplicated",
                    location=str(path),
                    row=index,
                    details={"transition_id": transition_id},
                )
            )
        seen.add(transition_id)
        if (
            row["from_role"].casefold() in HELD_OUT_ROLES
            and row["action"].casefold() in UPDATE_USAGES
            and row["from_model_version"] == row["to_model_version"]
        ):
            findings.append(
                _issue(
                    "E_QUERY_UPDATE_SAME_VERSION",
                    "L4",
                    "held-out query updates the same model version",
                    location=str(path),
                    row=index,
                    details={
                        "transition_id": transition_id,
                        "model_version": row["from_model_version"],
                    },
                    remediation="assign the post-query update a new model version",
                )
            )
        fresh = row["fresh_relative_to_previous_versions"].casefold()
        if fresh not in {"true", "yes", "1"}:
            findings.append(
                _issue(
                    "E_QUERY_NOT_FRESH",
                    "L4",
                    "query transition is not explicitly fresh relative to previous versions",
                    location=str(path),
                    row=index,
                    details={"transition_id": transition_id, "value": row["fresh_relative_to_previous_versions"]},
                    remediation="set fresh_relative_to_previous_versions=true only for a genuinely fresh query group",
                )
            )
        if row["from_model_version"] == row["to_model_version"]:
            findings.append(
                _issue(
                    "E_QUERY_VERSION_NOT_ADVANCED",
                    "L4",
                    "fresh-query transition must advance to a new model version",
                    location=str(path),
                    row=index,
                    details={
                        "transition_id": transition_id,
                        "model_version": row["from_model_version"],
                    },
                    remediation="bind the transition output to a new immutable model version",
                )
            )
    return findings, stats


def validate_artifact(
    path: Path,
    require_level: str = "L0",
    explain: bool = False,
) -> ValidationReport:
    """Validate an artifact and return its highest defensible evidence level.

    The validator never reads predictions, labels, scores, or model outcomes.
    ``explain`` is accepted for API symmetry with the CLI; it only affects
    serialization through :meth:`ValidationReport.to_dict`.
    """

    del explain
    try:
        required = normalize_level(require_level)
    except ValueError as exc:
        raise ArtifactError("E_REQUIRED_LEVEL", str(exc)) from exc
    root, config, files = load_config(Path(path))
    declared = config["declared_level"]
    findings: List[ValidationIssue] = []
    level_findings: Dict[str, List[ValidationIssue]] = {level: [] for level in LEVELS}
    statistics: Dict[str, Any] = {
        "segments": 0,
        "roles": [],
        "sources": 0,
        "acquisitions": 0,
        "physical_emitters": 0,
    }

    segments_path = files["segments"]
    valid_rows: List[Dict[str, Any]] = []
    evidence_cap = 4
    if not segments_path.is_file():
        level_findings["L0"].append(
            _issue(
                "E_SEGMENTS_MISSING",
                "L0",
                "segments.csv is required",
                location=str(segments_path),
                remediation="create the segment ledger using 'vlips init' or 'vlips demo'",
            )
        )
    else:
        headers, rows = _read_csv(segments_path, "E_SEGMENTS_MISSING", "segment ledger")
        missing_headers = [column for column in SEGMENT_COLUMNS if column not in headers]
        if missing_headers:
            level_findings["L0"].append(
                _issue(
                    "E_SEGMENTS_HEADER",
                    "L0",
                    "segment ledger is missing required columns",
                    location=str(segments_path),
                    details={"missing": missing_headers},
                    remediation="use the columns emitted by 'vlips schema export'",
                )
            )
        elif not rows:
            level_findings["L0"].append(
                _issue(
                    "E_SEGMENTS_EMPTY",
                    "L0",
                    "segment ledger contains no segments",
                    location=str(segments_path),
                    remediation="record at least one segment before validation",
                )
            )
        seen_segment_ids: Set[str] = set()
        for row_number, row in enumerate(rows, start=2):
            common_required = (
                "segment_id",
                "source_file_id",
                "sample_start",
                "sample_end",
                "model_version",
                "role",
                "usage",
            )
            missing_values = [column for column in common_required if not row.get(column, "").strip()]
            if missing_values:
                level_findings["L0"].append(
                    _issue(
                        "E_SEGMENT_REQUIRED_VALUE",
                        "L0",
                        "segment has missing values required for interval evidence",
                        location=str(segments_path),
                        row=row_number,
                        details={"missing": missing_values},
                        remediation="populate all interval, role, usage, and model-version fields",
                    )
                )
                continue
            segment_id = row["segment_id"]
            if segment_id in seen_segment_ids:
                level_findings["L0"].append(
                    _issue(
                        "E_SEGMENT_ID_DUPLICATE",
                        "L0",
                        "segment_id is duplicated",
                        location=str(segments_path),
                        row=row_number,
                        details={"segment_id": segment_id},
                    )
                )
                continue
            seen_segment_ids.add(segment_id)
            try:
                start = int(row["sample_start"])
                end = int(row["sample_end"])
            except ValueError:
                level_findings["L0"].append(
                    _issue(
                        "E_SAMPLE_BOUND_TYPE",
                        "L0",
                        "sample bounds must be integers",
                        location=str(segments_path),
                        row=row_number,
                    )
                )
                continue
            if start < 0 or end <= start:
                level_findings["L0"].append(
                    _issue(
                        "E_SAMPLE_BOUND_ORDER",
                        "L0",
                        "sample interval must satisfy 0 <= sample_start < sample_end",
                        location=str(segments_path),
                        row=row_number,
                        details={"sample_start": start, "sample_end": end},
                    )
                )
                continue
            enriched: Dict[str, Any] = dict(row)
            enriched["sample_start"] = start
            enriched["sample_end"] = end
            enriched["_row"] = row_number
            valid_rows.append(enriched)

            evidence = row.get("evidence_level", "").strip().casefold()
            if evidence in RESOLVED_EVIDENCE:
                row_cap = 4
            elif evidence.upper() in LEVEL_INDEX:
                row_cap = LEVEL_INDEX[evidence.upper()]
            elif evidence in UNRESOLVED_EVIDENCE:
                row_cap = 0
                level_findings["L1"].append(
                    _issue(
                        "E_EVIDENCE_UNRESOLVED",
                        "L1",
                        "segment evidence is unresolved, so claims above L0 are unavailable",
                        location=str(segments_path),
                        row=row_number,
                        details={"segment_id": segment_id},
                        remediation="resolve the segment lineage and record resolved or an explicit evidence level",
                        status="not_checkable",
                    )
                )
            else:
                row_cap = 0
                level_findings["L1"].append(
                    _issue(
                        "E_EVIDENCE_VALUE",
                        "L1",
                        "evidence_level is not recognized, so claims above L0 are unavailable",
                        location=str(segments_path),
                        row=row_number,
                        details={"segment_id": segment_id, "value": row.get("evidence_level", "")},
                        remediation="use resolved, verified, complete, unresolved, or L0-L4",
                        status="not_checkable",
                    )
                )
            evidence_cap = min(evidence_cap, row_cap)

        by_source: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in valid_rows:
            by_source[row["source_file_id"]].append(row)
        for source, source_rows in by_source.items():
            ordered = sorted(source_rows, key=lambda item: (item["sample_start"], item["sample_end"], item["segment_id"]))
            for index, left in enumerate(ordered):
                for right in ordered[index + 1 :]:
                    if right["sample_start"] >= left["sample_end"]:
                        break
                    if left["role"].casefold() != right["role"].casefold():
                        level_findings["L0"].append(
                            _issue(
                                "E_INTERVAL_ROLE_OVERLAP",
                                "L0",
                                "overlapping intervals from one source are assigned to different roles",
                                location=str(segments_path),
                                row=right["_row"],
                                details={
                                    "source_file_id": source,
                                    "segments": [left["segment_id"], right["segment_id"]],
                                    "roles": [left["role"], right["role"]],
                                },
                                remediation="move both intervals to one role or use non-overlapping boundaries",
                            )
                        )

        level_findings["L0"].extend(
            _cross_role_findings(
                valid_rows,
                "source_file_id",
                "L0",
                "E_SOURCE_ROLE_CROSSING",
                "source file",
                str(segments_path),
            )
        )
        for row in valid_rows:
            if not row.get("acquisition_id", "").strip():
                level_findings["L1"].append(
                    _issue(
                        "E_ACQUISITION_REQUIRED",
                        "L1",
                        "acquisition_id is required to prove L2",
                        location=str(segments_path),
                        row=row["_row"],
                        details={"segment_id": row["segment_id"]},
                    )
                )
            if not row.get("physical_emitter_id", "").strip():
                level_findings["L2"].append(
                    _issue(
                        "E_IDENTITY_REQUIRED",
                        "L2",
                        "physical_emitter_id is required to prove L2",
                        location=str(segments_path),
                        row=row["_row"],
                        details={"segment_id": row["segment_id"]},
                    )
                )
        level_findings["L1"].extend(
            _cross_role_findings(
                valid_rows,
                "acquisition_id",
                "L1",
                "E_ACQUISITION_ROLE_CROSSING",
                "acquisition",
                str(segments_path),
            )
        )
        level_findings["L2"].extend(
            _cross_role_findings(
                valid_rows,
                "physical_emitter_id",
                "L2",
                "E_IDENTITY_ROLE_CROSSING",
                "physical emitter",
                str(segments_path),
            )
        )

        statistics.update(
            {
                "segments": len(rows),
                "roles": sorted({row["role"].casefold() for row in valid_rows if row.get("role")}),
                "sources": len({row["source_file_id"] for row in valid_rows if row.get("source_file_id")}),
                "acquisitions": len({row["acquisition_id"] for row in valid_rows if row.get("acquisition_id")}),
                "physical_emitters": len({row["physical_emitter_id"] for row in valid_rows if row.get("physical_emitter_id")}),
            }
        )

    required_pipeline_bindings = {
        (
            _semantic_role(row["role"]),
            _semantic_usage(row["usage"]),
            row["model_version"],
        )
        for row in valid_rows
    }
    pipeline_findings, pipeline_stats = _validate_pipeline(
        files["pipeline_dependencies"], required_pipeline_bindings
    )
    transition_findings, transition_stats = _validate_transitions(files["query_transitions"])
    level_findings["L3"].extend(pipeline_findings)
    level_findings["L4"].extend(transition_findings)
    statistics.update(pipeline_stats)
    statistics.update(transition_stats)

    declared_index = LEVEL_INDEX[declared]
    if declared_index < 4:
        blocked_level = LEVELS[declared_index + 1]
        level_findings[blocked_level].append(
            _issue(
                "E_DECLARED_LEVEL_CAP",
                blocked_level,
                "artifact declaration does not claim the next evidence level",
                location=str(root / "vlips.yaml"),
                details={"declared_level": declared},
                remediation="raise declared_level only after supplying and validating the stronger evidence",
            )
        )

    if evidence_cap < 4:
        blocked_level = LEVELS[evidence_cap + 1]
        if not any(issue.code in {"E_EVIDENCE_UNRESOLVED", "E_EVIDENCE_VALUE"} and issue.level == blocked_level for issue in level_findings[blocked_level]):
            level_findings[blocked_level].append(
                _issue(
                    "E_EVIDENCE_LEVEL_CAP",
                    blocked_level,
                    "segment evidence declarations cap the highest provable level",
                    location=str(segments_path),
                    details={"evidence_cap": LEVELS[evidence_cap]},
                    remediation="supply lineage evidence at the required level for every segment",
                )
            )

    checks: Dict[str, Dict[str, Any]] = {}
    hierarchy_intact = True
    highest: Optional[str] = None
    for level in LEVELS:
        direct_pass = not level_findings[level]
        hierarchy_intact = hierarchy_intact and direct_pass
        statuses = {issue.status for issue in level_findings[level]}
        if not hierarchy_intact:
            if "fail" in statuses:
                status = "FAIL"
            elif "not_checkable" in statuses:
                status = "NOT_CHECKABLE"
            else:
                status = "NOT_CHECKABLE"
        else:
            status = "PASS"
        checks[level] = {
            "passed": hierarchy_intact,
            "status": status,
            "direct_findings": len(level_findings[level]),
        }
        if hierarchy_intact:
            highest = level
        findings.extend(level_findings[level])

    accepted = highest is not None and LEVEL_INDEX[highest] >= LEVEL_INDEX[required]
    return ValidationReport(
        artifact=str(root),
        required_level=required,
        highest_provable_level=highest,
        accepted=accepted,
        declared_level=declared,
        checks=checks,
        issues=findings,
        statistics=statistics,
    )
