# Examples

All examples in this directory are synthetic. Their identifiers do not refer to
a real device, person, recording, host, dataset, or filesystem path, and no RF
samples are included.

- [`minimal/`](minimal/) is a compact manifest for learning the CSV layout and
  validation workflow.
- [`candidates.csv`](candidates.csv) demonstrates deterministic outcome-blind
  selection using fictional structural counts.

Copy an example to a working directory before editing it. For a skeleton that
matches the installed package exactly, prefer:

```bash
vlips init my-split --level L2
```

Run the selector example with:

```bash
vlips select examples/candidates.csv --format text
```
