#!/usr/bin/env python3
"""Fail a release when it contains private, oversized, or bundled artifacts.

The audit intentionally uses only the Python standard library so it can run in
an isolated checkout before packaging or publishing.  It reports every finding
in a stable JSON structure and never modifies the tree it scans.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


SCHEMA_VERSION = "vlips-rf-release-audit-1.0"
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}
SUSPICIOUS_DIRECTORIES = {
    "3rdparty",
    "dependencies",
    "external",
    "externals",
    "submodules",
    "third-party",
    "third_party",
    "vendor",
    "vendored",
}
SUSPICIOUS_EXTENSIONS = {
    ".7z",
    ".a",
    ".bin",
    ".bz2",
    ".ckpt",
    ".dll",
    ".dylib",
    ".exe",
    ".gz",
    ".h5",
    ".joblib",
    ".key",
    ".mat",
    ".npy",
    ".npz",
    ".onnx",
    ".p12",
    ".pem",
    ".pkl",
    ".pickle",
    ".pt",
    ".pth",
    ".rar",
    ".safetensors",
    ".so",
    ".tar",
    ".tgz",
    ".whl",
    ".xz",
    ".zip",
}
TEXT_EXTENSIONS = {
    "",
    ".cfg",
    ".cff",
    ".csv",
    ".ini",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".rst",
    ".toml",
    ".tsv",
    ".txt",
    ".yaml",
    ".yml",
}
LEGAL_FILENAMES = {
    "citation.cff",
    "copying",
    "license",
    "license.md",
    "license.txt",
    "notice",
    "notice.md",
    "third_party_notices",
    "third_party_notices.md",
}


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    detail: str
    line: int | None = None


def _content_patterns() -> tuple[tuple[str, re.Pattern[str]], ...]:
    # Split sensitive examples so this scanner does not match its own source.
    prohibited_names = ("sealed" + "_query", "evaluator" + "_secret")
    drive_path = r"[A-Z]:" + r"\\" + r"(?:Users\\|[^\s'\"<>|]+\\)"
    unix_home_path = "/" + "home" + r"/[^/\s]+/"
    mac_home_path = "/" + "Users" + r"/[^/\s]+/"
    return (
        (
            "absolute_path",
            re.compile(f"(?i)(?:{drive_path}|{unix_home_path}|{mac_home_path})"),
        ),
        ("sealed_or_evaluator_material", re.compile("|".join(prohibited_names), re.I)),
        ("private_key", re.compile("-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
        ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b")),
        ("github_fine_grained_token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b")),
        ("openai_token", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
        ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
        ("google_api_key", re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b")),
        ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
        (
            "assigned_secret",
            re.compile(
                r"(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\b"
                r"\s*[:=]\s*['\"][^'\"\r\n]{12,}['\"]"
            ),
        ),
    )


def _display(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _iter_files(root: Path) -> Iterable[Path]:
    for current, directories, filenames in os.walk(root):
        directories[:] = sorted(
            name for name in directories if name.lower() not in IGNORED_DIRECTORIES
        )
        base = Path(current)
        for filename in sorted(filenames):
            yield base / filename


def audit_tree(root: Path, max_bytes: int = DEFAULT_MAX_BYTES) -> list[Finding]:
    """Return deterministic findings for *root* without changing any file."""
    root = root.resolve()
    findings: list[Finding] = []
    patterns = _content_patterns()

    for path in _iter_files(root):
        relative = _display(path, root)
        normalized_relative = relative.casefold()
        sensitive_names = ("sealed" + "_query", "evaluator" + "_secret")
        if any(name in normalized_relative for name in sensitive_names):
            findings.append(
                Finding(
                    "sealed_or_evaluator_material",
                    relative,
                    "prohibited material appears in the release path",
                )
            )
        relative_parts = {part.lower() for part in Path(relative).parts[:-1]}
        suspicious_parts = sorted(relative_parts & SUSPICIOUS_DIRECTORIES)
        if suspicious_parts:
            findings.append(
                Finding(
                    "suspicious_third_party_directory",
                    relative,
                    "directory=" + suspicious_parts[0],
                )
            )

        try:
            size = path.stat().st_size
        except OSError as exc:
            findings.append(Finding("unreadable_file", relative, str(exc)))
            continue

        if size > max_bytes:
            findings.append(
                Finding("oversized_file", relative, f"{size} bytes exceeds {max_bytes}")
            )

        extension = path.suffix.lower()
        if extension in SUSPICIOUS_EXTENSIONS:
            findings.append(
                Finding("suspicious_artifact_extension", relative, f"extension={extension}")
            )

        if path.name.lower() in LEGAL_FILENAMES or extension not in TEXT_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            findings.append(Finding("unreadable_text", relative, str(exc)))
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            for code, pattern in patterns:
                if pattern.search(line):
                    findings.append(Finding(code, relative, "matched prohibited content", line_number))

    return sorted(findings, key=lambda item: (item.path, item.line or 0, item.code))


def report(root: Path, findings: list[Finding], max_bytes: int) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if not findings else "fail",
        "root": str(root.resolve()),
        "policy": {"maximum_file_bytes": max_bytes},
        "finding_count": len(findings),
        "findings": [asdict(item) for item in findings],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.max_bytes < 1:
        print("--max-bytes must be positive", file=sys.stderr)
        return 2
    if not args.root.is_dir():
        print(f"not a directory: {args.root}", file=sys.stderr)
        return 2

    findings = audit_tree(args.root, args.max_bytes)
    payload = report(args.root, findings, args.max_bytes)
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
