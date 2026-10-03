"""The three-state verdict shared by every primitive.

Two booleans do not describe reality. A check can confirm a claim, contradict it,
or honestly report that the layer it runs in cannot see far enough to tell —
and that third state is the one pipelines usually throw away, which is exactly
how an unverifiable claim becomes a silently trusted one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Verdict(str, Enum):
    """Outcome of a proof check."""

    #: The evidence supports the claim.
    VERIFIED = "verified"
    #: The evidence contradicts the claim.
    REFUTED = "refuted"
    #: This layer cannot see enough to decide. Never treat as a pass.
    UNOBSERVABLE = "unobservable"

    def ok(self) -> bool:
        """True only for a real confirmation. UNOBSERVABLE is not a pass."""
        return self is Verdict.VERIFIED

    def gateable(self) -> bool:
        """True when a pipeline can safely branch on this verdict.

        UNOBSERVABLE is not gateable: it must be surfaced, not swallowed.
        """
        return self in (Verdict.VERIFIED, Verdict.REFUTED)


@dataclass
class Proof:
    """A verdict plus the machine-readable detail behind it."""

    verdict: Verdict
    subject: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)
    findings: List[str] = field(default_factory=list)

    def ok(self) -> bool:
        return self.verdict.ok()

    @property
    def summary(self) -> str:
        head = f"{self.subject or 'proof'}: {self.verdict.value}"
        return f"{head} ({len(self.findings)} finding(s))" if self.findings else head

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "subject": self.subject,
            "detail": self.detail,
            "findings": list(self.findings),
        }


def verified(subject: str = "", **detail: Any) -> Proof:
    return Proof(Verdict.VERIFIED, subject, detail)


def refuted(subject: str = "", findings: Optional[List[str]] = None, **detail: Any) -> Proof:
    return Proof(Verdict.REFUTED, subject, detail, findings or [])


def unobservable(subject: str = "", reason: str = "", **detail: Any) -> Proof:
    return Proof(Verdict.UNOBSERVABLE, subject, detail, [reason] if reason else [])
