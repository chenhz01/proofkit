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

### Fixed during development

- `attest.stamp` produced a region that differed from the hashed region by a
  trailing newline, so every stamped document was born stale. The region is now
  normalised with `rstrip()` on both sides.
- `check_idempotent` was documented as an idempotency check but only proved
  determinism. Both properties are now separate functions, each named for what
  it actually proves.
