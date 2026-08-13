# Third-party and data notices

## What the Apache-2.0 license covers

The repository's [LICENSE](LICENSE) applies to source code, documentation, and
synthetic examples authored for this V-LiPS-RF release, unless a file says
otherwise.

## What is not included or relicensed

This repository does **not** contain or relicense:

- raw or processed RF recordings, including the datasets used in the paper;
- dataset labels, sealed evaluation identities, or private split assignments;
- pretrained weights, checkpoints, predictions, or experiment results;
- third-party recognition-model source code;
- server inventories, credentials, private paths, or execution infrastructure;
- article PDFs or other copyrighted publication content.

Dataset access and use remain subject to each dataset provider's terms. A
manifest generated from a dataset is not permission to redistribute that
dataset. Users are responsible for obtaining the relevant data and model
licenses independently.

## Runtime and development dependencies

Installing or testing the package may install separately distributed Python
packages declared in `pyproject.toml`. Those packages remain under their own
licenses and are not relicensed by Apache-2.0. The source distribution does not
vendor their source trees.

## User-supplied material

Files passed to V-LiPS-RF remain user-supplied material. The project license
does not grant rights to publish identifiers, paths, measurements, labels, or
other content in those files. Use opaque identifiers and keep sensitive source
data outside the project directory whenever possible.

If a future release adds vendored material, its provenance, version, license,
and required notices must be recorded here before release.

