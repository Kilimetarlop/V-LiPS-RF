# Validation levels

V-LiPS-RF reports the highest compatibility level that is proved by the
artifact. Levels are cumulative. Requesting L3 means that L0, L1, L2, and L3
must all be proved.

| Level | Required evidence | Question answered |
|---|---|---|
| L0 | Valid rows plus exact interval and source-file separation. | Do incompatible roles avoid direct interval reuse and the same declared source file? |
| L1 | L0 and acquisition separation. | Do incompatible roles avoid the same declared acquisition? |
| L2 | L1 and physical-emitter separation under the policy. | Is the nominally unknown evaluation identity absent from roles prohibited by the policy? |
| L3 | L2 and complete pipeline reachability and model-version evidence. | Can final-query information reach a component used by the evaluated version? |
| L4 | L3 and fresh-query transitions after test-consuming updates. | Is every affected new version evaluated only with fresh queries? |

These levels describe evaluation evidence, not model accuracy. A classifier can
have high accuracy and fail L1. A manifest can pass L4 while the associated
classifier performs poorly.

## Cumulative and fail-closed behavior

For every assertion, V-LiPS-RF emits one of three states:

- `PASS`: evidence establishes the assertion;
- `FAIL`: evidence contradicts the assertion;
- `NOT CHECKABLE`: the artifact does not contain sufficient valid evidence.

The requested level is accepted only if every assertion required through that
level is `PASS`. Neither an absent row nor an absent auxiliary ledger is
interpreted as separation.

The highest proved level can be lower than the level named in the project
configuration. The configuration declares intent; it does not confer evidence.

## L0: interval and source isolation

The validator checks the interval `[sample_start, sample_end)` for each segment.
An end equal to another segment's start is not an overlap. Reuse of a prohibited
interval fails L0 even if the two rows have different segment IDs.

L0 also checks `source_file_id`. Use a stable logical or
content-derived identifier, not a machine-specific path. Renaming one physical
file to two identifiers would make the evidence false rather than make the
split valid.

L0 is intentionally narrow. It cannot detect related samples stored in
different declared sources or produced by the same acquisition unless that
relationship is declared at a higher level.

## L1: acquisition isolation

L1 requires L0 and checks `acquisition_id`. An acquisition should represent the
collection event whose shared conditions could connect two segments. Splitting
one recording session into several files does not create independent
acquisitions.

## L2: physical-emitter isolation

L2 requires L1 and checks `physical_emitter_id` under the artifact's declared
role policy. This is the level at which an unenrolled test emitter can be
distinguished from an emitter already used by a prohibited upstream role.

An emitter identifier may be pseudonymous, but it must remain stable across the
scope being validated. If cross-dataset emitter equivalence is unknown, the
validator cannot prove it.

## L3: pipeline and version closure

L3 requires L2 and complete reachability and model-version evidence. The
artifact declares which roles and artifacts can reach each evaluated component
and binds every component to its model version.

L3 rejects a prohibited reachable path even when an experiment reports no
numerical change. Numerical insensitivity is not proof that a path was absent.

## L4: fresh-query transitions

L4 requires L3 and transition evidence showing that every update which consumed
a held-out/final query created a new affected version evaluated on fresh
queries. The standard artifact uses:

- `pipeline_dependencies.json`, declaring which data roles and artifacts can
  reach each evaluated component;
- `query_transitions.csv`, binding test-consuming updates to a new model version
  and recording the fresh-query transition.

A cache, threshold, calibration state, or adaptation update that
consumes a final query belongs to a new affected version; it cannot remain
silently attached to the old version.

## Evidence boundary

The SDK checks declared metadata. It does not read RF payload bytes, infer
physical identity from waveforms, or reconstruct undocumented pipeline state.
For important evaluations, preserve source acquisition records, hash-bound
exports, and an independent audit trail in addition to the public manifest.
