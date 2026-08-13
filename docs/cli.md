# CLI reference

The `vlips` command operates on an artifact directory. It does not connect to a
dataset service, open RF payloads, or execute a model.

## `vlips demo`

```bash
vlips demo --out DIR
```

Creates a small, synthetic, redistributable artifact intended for the README
walkthrough. Existing user files are not required. Inspect the generated files
before using them as a template for a real protocol.

## `vlips init`

```bash
vlips init PATH --level L0|L1|L2|L3|L4
```

Creates an artifact skeleton and the evidence files required by the requested
level. The chosen level is a target, not a certificate: validation awards only
what the completed evidence proves.

## `vlips validate`

```bash
vlips validate PATH --require-level L0|L1|L2|L3|L4 [--explain] [--format text|json] [--report PATH]
```

Loads the artifact, evaluates cumulative assertions through the requested
level, and exits nonzero if any required assertion is `FAIL` or
`NOT CHECKABLE`.

- `--require-level` sets the minimum accepted level.
- `--explain` adds check-by-check evidence to text output.
- `--format text` produces a concise human report.
- `--format json` produces a machine-readable report on standard output.
- `--report PATH` writes the complete report to a separate file.

Validation is read-only with respect to the artifact. Redirect JSON output to a
separate report path if it must be retained.

## `vlips inspect`

```bash
vlips inspect PATH
```

Summarizes the configuration, row counts, declared roles, model versions, and
available evidence. Inspection does not award a level and should not be used as
a validation gate.

## `vlips schema export`

```bash
vlips schema export
```

Prints the schemas supported by the installed release. Use this output instead
of copying an unversioned schema from another project.

## `vlips select`

```bash
vlips select candidates.csv [--format text|json]
```

Rejects ineligible candidates, ranks the remaining rows using only prespecified
structural fields, and deterministically selects one representative. The fixed
header is:

```text
candidate_id,eligible,identity_count,acquisition_count,condition_count,role_imbalance,legal_signal_count,transfer_bytes
```

Counts describe structural coverage; `role_imbalance` and `transfer_bytes`
describe prespecified structural costs. An opaque `candidate_id` resolves an
exact tie. Test labels, predictions, scores, accuracy, loss, and other outcome
columns are prohibited and cause rejection. The selector neither trains nor
evaluates a model and does not claim that its representative has superior
predictive performance.

## Python SDK

The corresponding public entry points are available from `vlips_rf`:

```python
from pathlib import Path

from vlips_rf import inspect_artifact, select_candidate, validate_artifact

root = Path("artifact")
summary = inspect_artifact(root)
report = validate_artifact(root, require_level="L2")
selection = select_candidate(Path("examples/candidates.csv"))
```

The SDK returns structured values; consult docstrings for the exact type in the
installed release. The same fail-closed semantics apply to CLI and SDK calls.

## Automation contract

For shell automation, rely on exit codes `0`, `1`, and `2`. For report
automation, rely on documented JSON fields and diagnostic identifiers. Avoid
parsing formatted text, which may improve between compatible releases.
