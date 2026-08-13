"""Command line interface for V-LiPS-RF."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .artifact import create_demo, initialize_artifact, inspect_artifact
from .errors import ArtifactError
from .models import LEVELS, ValidationReport
from .schema import artifact_schema
from .selection import select_candidate
from .validation import validate_artifact


EXIT_OK = 0
EXIT_REJECTED = 1
EXIT_FATAL = 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vlips",
        description="Validate RF partition integrity without reading model outcomes.",
    )
    parser.add_argument("--version", action="version", version="vlips 0.1.0")
    commands = parser.add_subparsers(dest="command", required=True)

    demo = commands.add_parser("demo", help="create a ready-to-validate L4 demo")
    demo.add_argument("--out", required=True, type=Path, metavar="DIR")

    init = commands.add_parser("init", help="create an empty artifact scaffold")
    init.add_argument("path", type=Path, metavar="PATH")
    init.add_argument("--level", required=True, choices=LEVELS)

    validate = commands.add_parser("validate", help="validate an artifact")
    validate.add_argument("path", type=Path, metavar="PATH")
    validate.add_argument("--require-level", required=True, choices=LEVELS)
    validate.add_argument("--explain", action="store_true")
    validate.add_argument("--format", choices=("text", "json"), default="text")
    validate.add_argument("--report", type=Path, metavar="PATH", help="write the JSON report")

    inspect = commands.add_parser("inspect", help="summarize an artifact without changing it")
    inspect.add_argument("path", type=Path, metavar="PATH")

    select = commands.add_parser("select", help="select an eligible candidate without outcomes")
    select.add_argument("path", type=Path, metavar="CANDIDATES.csv")
    select.add_argument("--format", choices=("text", "json"), default="text")

    schema = commands.add_parser("schema", help="work with the artifact schema")
    schema_commands = schema.add_subparsers(dest="schema_command", required=True)
    schema_commands.add_parser("export", help="print the canonical schema as JSON")
    return parser


def _render_report(report: ValidationReport, explain: bool) -> str:
    verdict = "ACCEPT" if report.accepted else "REJECT"
    highest = report.highest_provable_level or "none"
    lines = [
        f"{verdict}: required={report.required_level} highest={highest} declared={report.declared_level}",
        (
            "segments={segments} roles={roles} sources={sources} acquisitions={acquisitions} "
            "physical_emitters={physical_emitters}"
        ).format(**report.statistics),
    ]
    errors = [
        issue
        for issue in report.issues
        if issue.to_dict(report.required_level)["severity"] == "error"
    ]
    warnings = len(report.issues) - len(errors)
    lines.append(f"findings: errors={len(errors)} warnings={warnings}")
    if explain:
        for issue in report.issues:
            payload = issue.to_dict(report.required_level, explain=True)
            location = payload.get("location", "")
            if "row" in payload:
                location = f"{location}:{payload['row']}"
            suffix = f" ({location})" if location else ""
            lines.append(
                f"- {payload['severity'].upper()} {payload['status'].upper()} "
                f"{payload['code']} [{payload['level']}]: "
                f"{payload['message']}{suffix}"
            )
            if payload.get("remediation"):
                lines.append(f"  remedy: {payload['remediation']}")
    elif report.issues:
        lines.append("run again with --explain to list findings and remedies")
    return "\n".join(lines)


def _fatal(exc: ArtifactError, as_json: bool) -> int:
    if as_json:
        print(json.dumps({"accepted": False, "fatal": exc.to_dict()}, indent=2, sort_keys=True))
    else:
        suffix = f" ({exc.path})" if exc.path else ""
        print(f"error[{exc.code}]: {exc.message}{suffix}", file=sys.stderr)
    return EXIT_FATAL


def main(argv: Optional[List[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            target = create_demo(args.out)
            print(f"created L4 demo: {target}")
            print(f"validate with: vlips validate \"{target}\" --require-level L4 --explain")
            return EXIT_OK
        if args.command == "init":
            target = initialize_artifact(args.path, args.level)
            print(f"initialized {args.level} artifact: {target}")
            return EXIT_OK
        if args.command == "validate":
            report = validate_artifact(args.path, args.require_level, explain=args.explain)
            report_payload = report.to_dict(explain=args.explain)
            if args.report is not None:
                try:
                    args.report.parent.mkdir(parents=True, exist_ok=True)
                    args.report.write_text(
                        json.dumps(report_payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                except OSError as exc:
                    raise ArtifactError(
                        "E_REPORT_WRITE",
                        "could not write the validation report",
                        path=str(args.report),
                        details={"reason": str(exc)},
                    ) from exc
            if args.format == "json":
                print(json.dumps(report_payload, indent=2, sort_keys=True))
            else:
                print(_render_report(report, args.explain))
            return EXIT_OK if report.accepted else EXIT_REJECTED
        if args.command == "inspect":
            print(json.dumps(inspect_artifact(args.path), indent=2, sort_keys=True))
            return EXIT_OK
        if args.command == "select":
            result = select_candidate(args.path)
            if args.format == "json":
                print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
            else:
                print(
                    f"selected={result.selected_candidate_id} "
                    f"eligible={result.eligible_count}/{result.candidate_count}"
                )
            return EXIT_OK
        if args.command == "schema" and args.schema_command == "export":
            print(json.dumps(artifact_schema(), indent=2, sort_keys=True))
            return EXIT_OK
    except ArtifactError as exc:
        return _fatal(exc, getattr(args, "format", None) == "json")
    parser.error("unsupported command")
    return EXIT_FATAL


if __name__ == "__main__":
    raise SystemExit(main())
