# V-LiPS-RF

V-LiPS-RF is a small, offline Python SDK and command-line tool for validating
radio-frequency (RF) split manifests and selecting a valid candidate without
looking at evaluation outcomes. It turns the evaluation-integrity rules from
the V-LiPS-RF paper into checks that can be run before model evaluation.

> **Scope:** this repository validates metadata and lineage evidence. It does
> not train a recognition model, ship a model checkpoint, read raw I/Q
> payloads, or include any original RF dataset. A passing report supports the
> declared split policy under the supplied evidence; it is not a claim that a
> model or split has the best predictive performance.

- Repository: <https://github.com/Kilimetarlop/V-LiPS-RF>
- Paper and citation status: [docs/paper.md](docs/paper.md)
- License and redistribution boundaries:
  [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

## What it does

V-LiPS-RF provides four related operations:

1. validate segment-level provenance and role assignments from a CSV manifest;
2. report each assertion as `PASS`, `FAIL`, or `NOT CHECKABLE`;
3. determine the highest evidenced compatibility level from L0 through L4;
4. select deterministically among safe candidates using declared structural
   coverage only, without reading labels, scores, or evaluation metrics.

The tool fails closed. Missing evidence is not silently treated as proof. If a
required assertion is `FAIL` or `NOT CHECKABLE`, the requested level is not
awarded.

## Five-minute quick start

V-LiPS-RF requires Python 3.9 or newer. From a clone of this repository:

```bash
python -m venv .venv
python -m pip install -e .
vlips demo --out vlips-demo
vlips inspect vlips-demo
vlips validate vlips-demo --require-level L2 --explain
```

The demo command creates a self-contained manifest with fictional identifiers.
The final command prints a check-by-check explanation and returns success only
when the evidence proves L2. To consume the report programmatically:

```bash
vlips validate vlips-demo --require-level L2 --format json
```

No network connection, GPU, RF payload, or model framework is needed.

## Start a project

```bash
vlips init my-split --level L2
```

Edit `my-split/segments.csv`, then validate it:

```bash
vlips validate my-split --require-level L2 --explain
```

The minimal CSV columns are:

```text
segment_id,physical_emitter_id,acquisition_id,source_file_id,sample_start,sample_end,model_version,role,usage,evidence_level
```

All identifiers should be stable, opaque identifiers rather than absolute
paths. `sample_start` is inclusive and `sample_end` is exclusive. See
[Manifest format](docs/manifest-format.md) for field semantics and
[examples/minimal](examples/minimal) for a synthetic input.

## Compatibility levels

Levels are cumulative: a higher level includes every requirement below it.

| Level | Evidence established |
|---|---|
| L0 | Exact interval and source-file separation across prohibited roles. |
| L1 | L0 plus acquisition separation. |
| L2 | L1 plus physical-emitter separation under the declared role policy. |
| L3 | L2 plus complete pipeline reachability and model-version evidence. |
| L4 | L3 plus a fresh-query transition after every test-consuming update. |

L0 does not mean "no leakage," and L2 does not establish L3 or L4. The highest
level is limited by the weakest required assertion and by the evidence actually
provided. Full definitions are in [Validation levels](docs/validation-levels.md).

## Result states

| State | Meaning |
|---|---|
| `PASS` | The supplied evidence proves the assertion under the declared policy. |
| `FAIL` | The supplied evidence contradicts the assertion. |
| `NOT CHECKABLE` | Required evidence is absent, malformed, or insufficient to decide. |

`NOT CHECKABLE` is intentionally different from `PASS`. With
`--require-level`, either `FAIL` or `NOT CHECKABLE` on a required assertion
causes a nonzero exit.

## Commands

```text
vlips demo --out DIR
vlips init PATH --level L0|L1|L2|L3|L4
vlips validate PATH --require-level L0|L1|L2|L3|L4 [--explain] [--format text|json]
vlips inspect PATH
vlips schema export
vlips select candidates.csv [--format text|json]
```

See [CLI reference](docs/cli.md) for outputs and automation guidance. Diagnostic
and process exit codes are documented in
[Statuses and errors](docs/statuses-and-errors.md).

## Outcome-blind selection

When candidate selection is used, unsafe candidates are rejected first. The
remaining candidates are ordered by prespecified structural coverage, and an
opaque canonical identifier resolves an exact tie. The selector must not read
test labels, predictions, scores, thresholds fitted from final queries, or
reported metrics. Determinism and outcome blindness make the choice auditable;
they do not make it predictively optimal.

The selector accepts this fixed CSV header:

```text
candidate_id,eligible,identity_count,acquisition_count,condition_count,role_imbalance,legal_signal_count,transfer_bytes
```

```bash
vlips select examples/candidates.csv --format text
```

Columns that expose outcomes (for example, accuracy, labels, predictions, or
scores) are rejected rather than ignored. See the [CLI reference](docs/cli.md).

## Python SDK

The public Python API exposes artifact initialization, inspection, schema
export, validation, and outcome-blind selection through `vlips_rf`. Public
names and signatures follow semantic versioning.

## Boundaries and responsible use

- Provide complete, truthful provenance. The tool cannot infer an undocumented
  relationship between emitters, acquisitions, files, caches, or versions.
- Hash or pseudonymize sensitive identifiers before sharing a manifest.
- Keep RF recordings, labels, checkpoints, credentials, hostnames, and private
  filesystem paths outside this repository.
- Raw-byte equivalence, model quality, statistical significance, deployment
  safety, and regulatory compliance are outside this package's scope.
- The Apache-2.0 license covers repository-authored software and documentation,
  not external datasets, papers, model implementations, or user-supplied data.

For the assumptions behind these statements, read the
[Threat model](docs/threat-model.md).

## Development

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md), do
not submit real RF data or secrets, and report security-sensitive problems as
described in [SECURITY.md](SECURITY.md).

## Citation

If V-LiPS-RF supports a publication, cite the software release using
[CITATION.cff](CITATION.cff) and cite the associated paper once its final
bibliographic record is available. The manuscript title and current citation
status are recorded in [docs/paper.md](docs/paper.md).
