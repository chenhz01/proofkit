"""Replay-based checks for stateful operations.

Two different properties get confused here, so both are provided explicitly:

* **determinism** — replaying a sequence from the same starting state produces
  the same final state every time. Non-determinism means something in the
  environment leaked into the computation.
* **idempotency** — applying a sequence twice is the same as applying it once
  (``f(f(x)) == f(x)``). This is the property that decides whether a retried job
  is harmless or a duplicate machine.

In a memory or agent store, idempotency is the difference between "the retry was
free" and "the retry doubled everything".

A single run proves nothing, so these replay several times and compare
fingerprints. Divergence is REFUTED; a run that cannot complete is
UNOBSERVABLE, never a pass.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence

from .verdict import Proof, Verdict

#: An operation is anything callable that maps state -> state.
Operation = Callable[[Dict[str, Any]], Dict[str, Any]]


def fingerprint(state: Mapping[str, Any]) -> str:
    """Stable hash of a state mapping, order-independent at the key level."""
    payload = json.dumps(state, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def replay(operations: Sequence[Operation], initial: Mapping[str, Any]) -> Dict[str, Any]:
    """Apply *operations* in order to a copy of *initial*."""
    state: Dict[str, Any] = dict(initial)
    for op in operations:
        state = op(state)
    return state


def check_idempotent(
    operations: Sequence[Operation],
    initial: Mapping[str, Any],
    runs: int = 3,
) -> Proof:
    """Replay *operations* several times and require identical fingerprints.

    This checks **determinism**: one input, one output, every time. For
    idempotency proper (``f(f(x)) == f(x)``) see :func:`check_idempotent_once`.

    :param runs: how many times to replay; 1 is refused, since a single run
        cannot demonstrate determinism.
    """
    if runs < 2:
        return Proof(
            Verdict.UNOBSERVABLE,
            "determinism",
            {"runs": runs},
            ["need at least 2 replays to demonstrate determinism"],
        )
    if not operations:
        return Proof(
            Verdict.UNOBSERVABLE,
            "determinism",
            {"runs": runs},
            ["no operations supplied: an empty sequence is trivially stable"],
        )

    prints: List[str] = []
    errors: List[str] = []
    for i in range(runs):
        try:
            prints.append(fingerprint(replay(operations, initial)))
        except Exception as exc:  # noqa: BLE001 - any failure is a finding
            errors.append(f"replay {i + 1} raised {type(exc).__name__}: {exc}")

    if errors:
        return Proof(Verdict.REFUTED, "determinism", {"runs": runs}, errors)

    if len(set(prints)) != 1:
        return Proof(
            Verdict.REFUTED,
            "determinism",
            {"runs": runs, "distinct_states": len(set(prints))},
            [f"replay produced {len(set(prints))} distinct states from one input"],
        )

    return Proof(Verdict.VERIFIED, "determinism", {"runs": runs, "fingerprint": prints[0]})


def check_idempotent_once(
    operations: Sequence[Operation],
    initial: Mapping[str, Any],
) -> Proof:
    """Check idempotency proper: applying the sequence twice equals applying it once.

    This is the check that matters for retries: a retried job must land in the
    same state, not a second copy of it.
    """
    if not operations:
        return Proof(
            Verdict.UNOBSERVABLE,
            "idempotency",
            {},
            ["no operations supplied: an empty sequence is trivially idempotent"],
        )

    try:
        once = fingerprint(replay(operations, initial))
        twice = fingerprint(replay(operations, replay(operations, initial)))
    except Exception as exc:  # noqa: BLE001
        return Proof(
            Verdict.REFUTED,
            "idempotency",
            {},
            [f"replay raised {type(exc).__name__}: {exc}"],
        )

    if once == twice:
        return Proof(Verdict.VERIFIED, "idempotency", {"fingerprint": once})

    return Proof(
        Verdict.REFUTED,
        "idempotency",
        {"once": once, "twice": twice},
        ["applying the sequence twice does not equal applying it once"],
    )


def set_ops(pairs: Iterable[tuple]) -> List[Operation]:
    """Build operations that assign ``pairs`` into state, last write winning."""

    def make(key: str, value: Any) -> Operation:
        def op(state: Dict[str, Any]) -> Dict[str, Any]:
            state[key] = value
            return state

        return op

    return [make(k, v) for k, v in pairs]
