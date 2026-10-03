"""The phase invariant: nothing gets consumed before it is verified.

A produced artifact must pass verification before anything downstream consumes
it. When a pipeline skips the verify step — or worse, consumes first and
verifies later — every downstream result is built on an unchecked input, and
nothing in the logs says so.

The trace vocabulary is deliberately small: if the layer cannot represent a
phase, the answer is UNOBSERVABLE rather than a guess.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Tuple

from .verdict import Proof, Verdict

PRODUCE = "produce"
VERIFY = "verify"
CONSUME = "consume"

_ORDER: Dict[str, int] = {PRODUCE: 1, VERIFY: 2, CONSUME: 3}

Trace = Sequence[Tuple[str, str]]


def check_phases(trace: Trace) -> Proof:
    """Check the produce → verify → consume ordering for every artifact.

    :param trace: ordered ``(operation, artifact_id)`` pairs as the pipeline
        actually executed them.
    """
    trace = list(trace)
    if not trace:
        return Proof(
            Verdict.UNOBSERVABLE,
            "phases",
            {"reason": "empty trace"},
            ["no operations recorded: nothing observed, nothing proven"],
        )

    unknown_ops = sorted({op for op, _ in trace if op not in _ORDER})
    if unknown_ops:
        return Proof(
            Verdict.UNOBSERVABLE,
            "phases",
            {"unknown_ops": unknown_ops},
            [f"layer emitted operations this check cannot model: {', '.join(unknown_ops)}"],
        )

    by_artifact: Dict[str, List[int]] = {}
    labels: Dict[str, List[str]] = {}
    for op, artifact in trace:
        by_artifact.setdefault(artifact, []).append(_ORDER[op])
        labels.setdefault(artifact, []).append(op)

    findings: List[str] = []
    for artifact, steps in by_artifact.items():
        if steps != sorted(steps):
            findings.append(f"{artifact}: {', '.join(labels[artifact])} is out of order")
        elif _ORDER[VERIFY] not in steps:
            findings.append(f"{artifact}: consumed without a verify step")

    consumed_unverified = [
        a for a, steps in by_artifact.items() if _ORDER[CONSUME] in steps and _ORDER[VERIFY] not in steps
    ]

    if findings:
        return Proof(
            Verdict.REFUTED,
            "phases",
            {
                "artifacts": len(by_artifact),
                "consumed_unverified": consumed_unverified,
            },
            findings,
        )
    return Proof(Verdict.VERIFIED, "phases", {"artifacts": len(by_artifact)})


def unverified_consumers(trace: Iterable[Tuple[str, str]]) -> List[str]:
    """Artifacts that reached CONSUME with no VERIFY on record."""
    seen: Dict[str, set] = {}
    for op, artifact in trace:
        if op in _ORDER:
            seen.setdefault(artifact, set()).add(op)
    return [a for a, ops in seen.items() if CONSUME in ops and VERIFY not in ops]
