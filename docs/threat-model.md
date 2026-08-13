# Threat model and claim boundary

V-LiPS-RF addresses accidental or intentional information paths that are
represented in an RF evaluation manifest and its auxiliary ledgers. Its central
question is whether information associated with a final query can influence a
component used by the evaluated model version under the declared policy.

## In scope

- exact sample-interval reuse;
- shared source files, acquisitions, and physical emitters across prohibited
  roles;
- declared pipeline dependencies from final-query information to preprocessing,
  calibration, selection, cache, adaptation, or decision state;
- test-consuming updates that are not bound to a new version and fresh queries;
- missing or unresolved evidence needed to prove a requested level;
- outcome-dependent candidate choice when using the supplied selector.

## Trust assumptions

The validator assumes that:

- manifest identifiers faithfully refer to real entities;
- upstream identity and acquisition resolution is accurate;
- the declared role policy matches actual data use;
- auxiliary dependency and transition ledgers describe the complete relevant
  pipeline;
- files have not been replaced outside any separately maintained hash or
  signature process.

The SDK checks consistency; it cannot make a false declaration true.

## Out of scope

- inspecting or comparing raw RF/IQ bytes;
- discovering duplicated recordings by signal similarity;
- training, evaluating, ranking, or certifying recognition models;
- proving statistical significance or predictive superiority;
- malware isolation and safe execution of untrusted code;
- data anonymization and legal or regulatory compliance;
- availability, side-channel, or hardware attacks;
- hidden state or dependencies omitted from the artifact.

## Why zero effect is not a pass

A prohibited path may reach a component without changing the final aggregate
metric. The component can be insensitive, a response may not cross the local
decision boundary, or individual changes may cancel in aggregate. Therefore
V-LiPS-RF validates path admissibility before outcome inspection; an observed
zero delta cannot override a prohibited dependency.

## Privacy and publication

Public artifacts should contain only the minimum metadata required for an
independent integrity check. Prefer opaque stable IDs, keep the private mapping
offline, and review each artifact for paths, hostnames, serial numbers,
credentials, and joinable identifiers. The repository's synthetic examples are
not derived from a real device or dataset.

