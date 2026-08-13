# Associated research

V-LiPS-RF accompanies the manuscript:

> **Beyond Split Leakage: Path–Response–Impact Analysis and V-LiPS-RF for
> Exposure-Resilient Open-Set UAV RF Evaluation**

Repository: <https://github.com/Kilimetarlop/V-LiPS-RF>

The final publisher bibliographic record and DOI are not yet available in this
release. They will replace this status note after publication. Until then, cite
the archived software release using `CITATION.cff` and identify the manuscript
by title; do not invent a DOI, volume, issue, or page range.

## Relationship between paper and software

The paper introduces Path–Response–Impact (PRI) to separate a prohibited
information path, the induced component/query response, and the decision-level
impact. This repository implements the prevention-facing portion as a compact
manifest validator and outcome-blind candidate selector.

The repository is intentionally smaller than the research environment. It does
not reproduce model training, distribute datasets, or contain the private
experimental infrastructure. Its purpose is to let another project express and
check the V-LiPS-RF evidence contract without inheriting that environment.

