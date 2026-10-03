"""Proof primitives for agent pipelines.

An agent that reports "done" and a pipeline that can *prove* it are different
things. This package supplies the missing layer: small, composable checks that
turn a claim into a three-state verdict you can gate on.

    from proofkit import Verdict, attest, closure, phases, idempotency

    if attest.verify(report_text, expected_digest) is not Verdict.VERIFIED:
        ...

Every primitive returns a :class:`Verdict` rather than a bare bool, because the
honest answer is often "this layer cannot see enough to tell" — and collapsing
that into ``False`` is how pipelines end up blocking on unknowns or waving real
problems through.
"""

from .verdict import Proof, Verdict
from . import attest, closure, phases, idempotency

__all__ = [
    "Verdict",
    "Proof",
    "attest",
    "closure",
    "phases",
    "idempotency",
    "__version__",
]

__version__ = "0.1.0"
