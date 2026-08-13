# Security policy

## Supported versions

Security and integrity fixes are applied to the latest 0.1.x release during the
initial public-development period. Older snapshots may not receive fixes.

## Reporting a vulnerability

Please use the repository's private **Security > Report a vulnerability**
workflow at <https://github.com/Kilimetarlop/V-LiPS-RF/security/advisories/new>.
Do not place credentials, private manifests, device identifiers, raw RF data,
or exploit details in a public issue.

Include the affected version, operating system, Python version, minimal
synthetic input, expected behavior, observed behavior, and potential impact.
Maintainers will acknowledge a complete report on a best-effort basis and will
coordinate disclosure after a fix is available.

## Security boundary

V-LiPS-RF is an offline metadata validator, not a sandbox or malware scanner.
Run it with ordinary user privileges. Treat manifests from untrusted parties as
untrusted files, inspect them before use, and do not follow paths or URLs that
they contain without independent verification.

The validator can detect contradictions and missing evidence represented in
its schemas. It cannot discover omitted relationships, prove that an upstream
export was honest, anonymize a dataset, or certify deployment security. A
`PASS` result must therefore be interpreted only within the declared policy and
the supplied evidence.

