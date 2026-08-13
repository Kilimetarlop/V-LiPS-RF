# Statuses, diagnostics, and exit codes

V-LiPS-RF separates assertion states from process exit codes. This lets a human
understand *why* evidence was rejected while automation receives a small,
stable result code.

## Assertion states

| State | Interpretation | Required-level consequence |
|---|---|---|
| `PASS` | The evidence establishes the assertion. | Satisfies the assertion. |
| `FAIL` | The evidence contradicts the assertion. | Rejects the requested level. |
| `NOT CHECKABLE` | Evidence is missing, malformed, or insufficient. | Rejects the requested level. |

The JSON report includes machine-readable diagnostic identifiers alongside a
human-readable message and, where possible, an evidence location. Diagnostic
identifiers are the error codes to use in tests and integrations; do not parse
English wording.

Use `--explain` for a check-by-check text report:

```bash
vlips validate my-split --require-level L3 --explain
```

Use JSON for automation:

```bash
vlips validate my-split --require-level L3 --format json
```

## Process exit codes

| Exit | Meaning |
|---:|---|
| `0` | Command completed successfully; for `validate`, the requested level was accepted. |
| `1` | The artifact was readable, but validation rejected the requested level. At least one required assertion is `FAIL` or `NOT CHECKABLE`. |
| `2` | Usage, configuration, input/output, or parsing error prevented a valid artifact evaluation. |

Exit 1 is an expected validation result, not a crash. Exit 2 means the caller
should repair the invocation or artifact structure before interpreting check
results.

## Common diagnostic categories

The exact diagnostic identifiers are emitted by the installed release and can
be inspected in JSON output. They cover these stable categories:

| Category | Typical cause | Action |
|---|---|---|
| Schema | Missing column, invalid value, duplicate ID, or malformed auxiliary file. | Compare the artifact with `vlips schema export`. |
| Interval | Invalid interval or prohibited overlap. | Correct the declared source coordinates; do not rename IDs to hide reuse. |
| Source | A source file reaches incompatible roles. | Rebuild the split from independent sources or lower the requested claim. |
| Acquisition | One acquisition reaches incompatible roles. | Group the complete acquisition before assignment. |
| Identity | A physical emitter reaches a prohibited upstream and final-query role. | Reassign at the physical-emitter level. |
| Reachability | A final-query dependency can reach an evaluated component. | Remove the path or bind the affected component to a new version. |
| Transition | A query-consuming update lacks a fresh-query version transition. | Create a new version and evaluate it on a fresh query set. |
| Evidence | A required relation is unresolved. | Supply valid provenance; absence is not separation. |

## CI pattern

```bash
vlips validate artifact --require-level L3 --format json --report vlips-report.json
```

The shell exit code is sufficient for a gate. Retain the JSON report as a build
artifact so the rejected assertion and evidence location remain reviewable.
Do not convert exit 1 to success merely because the model metrics look good.
