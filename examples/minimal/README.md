# Minimal synthetic artifact

This artifact uses fictional IDs and contains metadata only. It demonstrates
separate physical emitters, acquisitions, source files, and intervals for three
roles associated with one model version.

```bash
vlips inspect examples/minimal
vlips validate examples/minimal --require-level L2 --explain
```

The example is deliberately small and is not evidence about a real dataset.
Its `evidence_level` values explicitly cap the claim at L2; it contains no L3
pipeline closure or L4 fresh-query transition evidence.
Use `vlips init PATH --level LEVEL` to generate a new artifact before recording
your own provenance.
