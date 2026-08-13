# Contributing to V-LiPS-RF

Thank you for helping make RF evaluation protocols easier to audit.

## Set up a development environment

```bash
python -m venv .venv
python -m pip install -e .
python -m unittest discover -s tests -v
```

Keep changes focused and include a regression test for behavior changes. A
public interface change should update the CLI help, README, and relevant file
under `docs/` in the same pull request.

## Design rules

- Fail closed: absent evidence must not become an implicit pass.
- Keep `PASS`, `FAIL`, and `NOT CHECKABLE` semantically distinct.
- Do not read labels, predictions, scores, or evaluation metrics when selecting
  a candidate.
- Keep deterministic tie-breaking independent of host paths and row order.
- Report the assertion and evidence location that caused a rejection.
- Do not claim predictive superiority from a lineage or integrity result.

## Test data and privacy

Only synthetic, redistributable fixtures may be committed. Never submit real RF
recordings, private device identifiers, labels, checkpoints, predictions,
credentials, hostnames, server inventories, or absolute filesystem paths.
Replace identifying values with opaque fictional IDs and keep fixtures small.

## Pull requests

Before opening a pull request:

1. run the complete test suite;
2. run the five-minute README quick start in a clean directory;
3. confirm that `git diff` contains no generated data or secrets;
4. explain any compatibility or schema change;
5. update `THIRD_PARTY_NOTICES.md` if vendored material is introduced.

By submitting a contribution, you agree that it is licensed under the
repository's Apache License, Version 2.0, and that you have the right to submit
it under those terms.

For sensitive reports, follow [SECURITY.md](SECURITY.md) instead of opening a
public issue.
