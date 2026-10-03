# proofkit

**Proof primitives for agent pipelines.** Zero runtime dependencies.

An agent that reports "done" and a pipeline that can *prove* it are different
things. This package is the missing layer between them: four small composable
checks that turn a claim into a **three-state verdict** you can gate on.

```python
from proofkit import Verdict, attest, closure, phases, idempotency

if attest.verify(report_text) is not Verdict.VERIFIED:
    block_the_release()
```

---

## The idea: three states, not two

Most checks return a bool, and that forces every "I cannot tell" into `False`.
That is how an unverifiable claim becomes a silently trusted one. Every primitive
here returns a `Verdict` instead:

| Verdict | Meaning | `ok()` |
|---|---|---|
| `VERIFIED` | the evidence supports the claim | `True` |
| `REFUTED` | the evidence contradicts the claim | `False` |
| `UNOBSERVABLE` | this layer cannot see enough to decide | **`False`** |

`UNOBSERVABLE` is never a pass. `ok()` returns `False` for it and `gateable()`
returns `False`, so a pipeline has to decide what to do with it rather than
inheriting a silent yes.

```python
>>> Verdict.UNOBSERVABLE.ok()
False
>>> Verdict.UNOBSERVABLE.gateable()
False
```

---

## The four primitives

### `attest` — an attestation that survives being written into the document

Hash a report, then write the hash into the report, and the write changes the
content you hashed. The stamp is stale the moment it lands, and a mismatch looks
exactly like "somebody edited the file". `attest` pins the hash scope to the
content *above* the attestation marker, so writing the digest cannot invalidate
it while any real edit still does.

```python
from proofkit import attest

stamped = attest.stamp("# Report\n\n## Findings\nThe adapter is a God class.\n")
attest.verify(stamped).verdict          # Verdict.VERIFIED
attest.verify(stamped + "tampered").verdict  # Verdict.REFUTED
```

### `closure` — is the evidence actually in force?

A pipeline says "verified" because some evidence was green. The question nobody
asks is whether that evidence still holds: a passing run on a branch nobody
merged, a receipt pointing at a reverted commit.

```python
from proofkit import closure

claims = [closure.Claim("witness", [closure.Evidence("abc1234", merged=False)])]
closure.check_closure(claims).verdict   # Verdict.REFUTED
closure.merged_commits(claims)          # {"witness": []} — nothing safe to build on
```

### `phases` — nothing gets consumed before it is verified

```python
from proofkit import phases

phases.check_phases([("produce", "a"), ("verify", "a"), ("consume", "a")]).verdict
# Verdict.VERIFIED
phases.check_phases([("produce", "a"), ("consume", "a")]).verdict
# Verdict.REFUTED — consumed without a verify step
```

If the layer emits an operation the check cannot model, the answer is
`UNOBSERVABLE`, not a guess.

### `idempotency` — is a retry free?

Two properties that are easy to confuse, so both are explicit:

```python
from proofkit import idempotency

def counting(state):                    # deterministic, but NOT idempotent
    state["n"] = state.get("n", 0) + 1
    return state

idempotency.check_idempotent([counting], {}).verdict         # VERIFIED (determinism)
idempotency.check_idempotent_once([counting], {}).verdict   # REFUTED (f(f(x)) != f(x))
```

The second one is the retry hazard: an operation that accumulates turns a retried
job into duplicated work.

---

## Install

```bash
pip install proofkit
```

Python 3.9+, no runtime dependencies. From a checkout:

```bash
pip install -e ".[dev]"
python -m pytest
```

## Design notes

- **Pure functions, no I/O.** Every check takes data and returns a `Proof`. Nothing
  touches the network, the clock, or the filesystem, so results are reproducible.
- **No hidden state.** Operations you pass in are called exactly as given; the
  initial state is never mutated.
- **Failures are findings, not tracebacks.** An operation that raises is reported
  as `REFUTED` with the exception in `findings`, because a crashing check is not
  a passing check.

## Limitations

- `closure` trusts the `merged` flag you give it. Wiring that flag to real merge
  state is your job; this library checks the logic around it, not the GitHub API.
- `phases` models three operations. Richer pipelines need to map their own events
  onto produce/verify/consume, and anything unmappable becomes `UNOBSERVABLE`.
- `attest` normalises trailing whitespace before hashing, so a whitespace-only
  edit at the end of the attested region is not detected.
- `idempotency` compares state fingerprints. Two different states that serialise
  identically are treated as the same state.

## License

MIT — see [LICENSE](LICENSE).
