# Changelog

## [0.1.0] - 2026-10-04

First release. All four primitives were written after hitting the failure they
address while reviewing agent pipelines in other projects.

### Added

- `attest` — attestation that survives being written into the document. Fixes
  self-invalidating hashes, where writing the digest changes the content that
  was hashed.
- `closure` — evidence-chain closure. Refuses to call a claim verified when its
  support is unmerged, unpinned, or absent.
- `phases` — the produce → verify → consume invariant, so nothing is consumed
  before it is checked.
- `idempotency` — `check_idempotent` for replay determinism and
  `check_idempotent_once` for true idempotency (`f(f(x)) == f(x)`), plus
  `set_ops` helpers.
- `verdict` — the shared three-state `Verdict` / `Proof` types.

### Fixed after the first release candidate

- `py.typed` was missing while the metadata advertised `Typing :: Typed`, so the
  package's annotations were invisible to type checkers despite the classifier.
  The PEP 561 marker now ships with the package, and a regression test fails if
  the marker and the classifier ever disagree again.
- CI never ran on a version tag, which would have made the `publish` job
  unreachable, and that job lacked `id-token: write`, which Trusted publishing
  needs to mint its OIDC token. Both are fixed; the tag trigger and the
  permission are now covered by the same review as any other change.
- CI pinned `actions/download-artifact` to `fa0a91b8…` as `v4`; that commit is a
  2024-07-05 v3-era commit. v4 resolves to `d3f86a10…` (2025-04-24) and the pin
  now matches.

### Fixed during development

- `attest.stamp` produced a region that differed from the hashed region by a
  trailing newline, so every stamped document was born stale. The region is now
  normalised with `rstrip()` on both sides.
- `check_idempotent` was documented as an idempotency check but only proved
  determinism. Both properties are now separate functions, each named for what
  it actually proves.
