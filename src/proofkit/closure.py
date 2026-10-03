"""Closure checking for evidence chains.

A pipeline says "verified" because some evidence was green. The question nobody
asks is whether that evidence is actually *in force*: a passing check on a
feature branch, a run nobody merged, a receipt pointing at a commit that was
later reverted.

This module walks a set of evidence and reports claims whose support is not
load-bearing. It never invents a pass: evidence it cannot classify comes back as
UNOBSERVABLE.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .verdict import Proof, Verdict

_SHA = re.compile(r"^[0-9a-f]{7,40}$")


@dataclass
class Evidence:
    """One supporting item for a claim.

    :param ref: what the claim cites — a commit sha, a branch name, a URL.
    :param merged: True only when the cited work is actually in force.
    :param kind: free-form label (``"commit"``, ``"run"``, ``"branch"``).
    """

    ref: str
    merged: bool
    kind: str = "commit"

    @property
    def looks_like_sha(self) -> bool:
        return bool(_SHA.match(self.ref.strip()))


@dataclass
class Claim:
    """A statement plus the evidence offered for it."""

    name: str
    evidence: List[Evidence] = field(default_factory=list)

    @property
    def unmerged(self) -> List[Evidence]:
        return [e for e in self.evidence if not e.merged]


def check_closure(
    claims: Iterable[Claim],
    require_merged: bool = True,
) -> Proof:
    """Check that every claim is backed by evidence that is actually in force.

    :param require_merged: when True, evidence not marked ``merged`` refutes the
        claim. When False it is reported but does not decide the verdict.
    """
    claims = list(claims)
    if not claims:
        return Proof(
            Verdict.UNOBSERVABLE,
            "closure",
            {"reason": "no claims supplied"},
            ["nothing to check: closure of an empty set proves nothing"],
        )

    findings: List[str] = []
    unverifiable: List[str] = []
    dangling: List[str] = []

    for claim in claims:
        if not claim.evidence:
            unverifiable.append(f"{claim.name}: no evidence offered")
            continue
        for ev in claim.evidence:
            if not ev.looks_like_sha and ev.kind in ("commit", "blob"):
                dangling.append(f"{claim.name}: evidence {ev.ref!r} is not a pinned object id")
        if require_merged and claim.unmerged:
            for ev in claim.unmerged:
                findings.append(
                    f"{claim.name}: cites {ev.ref} ({ev.kind}) which is not merged/in force"
                )

    if findings:
        return Proof(
            Verdict.REFUTED,
            "closure",
            {"claim_count": len(claims), "unmerged": len(findings)},
            findings + dangling,
        )
    if unverifiable or dangling:
        return Proof(
            Verdict.UNOBSERVABLE,
            "closure",
            {"claim_count": len(claims)},
            unverifiable + dangling,
        )
    return Proof(Verdict.VERIFIED, "closure", {"claim_count": len(claims)})


def merged_commits(claims: Iterable[Claim]) -> Dict[str, List[str]]:
    """Map claim name -> the refs that are actually merged.

    The safe subset: what you are allowed to build on.
    """
    out: Dict[str, List[str]] = {}
    for claim in claims:
        out[claim.name] = [e.ref for e in claim.evidence if e.merged]
    return out
