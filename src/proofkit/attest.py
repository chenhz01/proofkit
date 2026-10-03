"""Attestation that survives being written into the document.

The bug this exists to prevent: you hash a report, then write the hash into the
report. The write changes the content you hashed, so the attestation is stale the
moment it lands — and nothing tells you, because a hash mismatch looks exactly
like "somebody edited the file".

The fix is to pin the hash scope. Everything above the attestation marker is the
attested region; the marker section itself is excluded. Writing the digest then
cannot invalidate it, while any real edit to the content still does.
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional

from .verdict import Proof, Verdict

#: Section that carries the digest, excluded from the hashed region.
DEFAULT_MARKER = "## Attestation"

_DIGEST_RE = re.compile(r"\b(?:sha256|hash)\s*[:=]\s*`?([0-9a-f]{64})`?", re.IGNORECASE)


def digest(data: bytes) -> str:
    """SHA-256 of *data* as lowercase hex."""
    return hashlib.sha256(data).hexdigest()


def attested_region(text: str, marker: str = DEFAULT_MARKER) -> str:
    """The part of *text* an attestation is allowed to cover.

    Content before *marker*. When the marker is absent the whole document is the
    region, which keeps plain files hashable.
    """
    return text.split(marker, 1)[0]


def content_digest(text: str, marker: str = DEFAULT_MARKER) -> str:
    """Digest of the attested region of *text*.

    Trailing whitespace is normalised. Without this, appending the attestation
    block would itself change the region being hashed and every stamped document
    would be born stale -- the exact bug this module exists to prevent.
    """
    return digest(attested_region(text, marker).rstrip().encode("utf-8"))


def stamp(text: str, marker: str = DEFAULT_MARKER, label: str = "sha256") -> str:
    """Return *text* with a correct attestation appended under *marker*.

    Idempotent: stamping an already-stamped document replaces the digest rather
    than appending a second block.
    """
    body = text
    if marker in text:
        body = re.sub(rf"{re.escape(marker)}.*\Z", "", text, flags=re.DOTALL)
    body = body.rstrip()
    new_digest = digest(body.encode("utf-8"))
    return f"{body}\n\n{marker}\n\n{label}: {new_digest}\n"


def extract_stamp(text: str) -> Optional[str]:
    """Pull the digest out of an attestation block, or None if absent."""
    marker_at = text.find(DEFAULT_MARKER)
    scope = text[marker_at:] if marker_at != -1 else text
    m = _DIGEST_RE.search(scope)
    return m.group(1) if m else None


def verify(text: str, expected: Optional[str] = None, marker: str = DEFAULT_MARKER) -> Proof:
    """Verify the attestation on *text*.

    With *expected* given, compares against it. Otherwise reads the document's
    own stamp — useful for "has this drifted since it was stamped?" checks.

    A missing stamp is UNOBSERVABLE, not VERIFIED: no attestation is not a
    passing attestation.
    """
    actual = content_digest(text, marker)
    if expected is None:
        expected = extract_stamp(text)
        if expected is None:
            return Proof(
                Verdict.UNOBSERVABLE,
                "attestation",
                {"reason": "no attestation block found", "marker": marker},
                [f"document has no {marker!r} block to verify against"],
            )
        source = "self-stamp"
    else:
        source = "expected"

    if expected == actual:
        return Proof(
            Verdict.VERIFIED,
            "attestation",
            {"digest": actual, "source": source},
        )

    return Proof(
        Verdict.REFUTED,
        "attestation",
        {"expected": expected, "actual": actual, "source": source},
        ["content above the attestation marker changed since it was stamped"],
    )
