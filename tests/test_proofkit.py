"""Every primitive must fire on the failure it was built for, and — critically —
must report UNOBSERVABLE rather than a false VERIFIED when it cannot see."""

import pytest

from proofkit import Verdict, attest, closure, idempotency, phases


# --------------------------------------------------------------------------- #
# attest: the self-invalidating hash
# --------------------------------------------------------------------------- #

DRAFT = "# Report\n\n## Findings\nThe adapter is a God class.\n"


def test_stamp_survives_being_written_into():
    stamped = attest.stamp(DRAFT)
    proof = attest.verify(stamped)
    assert proof.verdict is Verdict.VERIFIED, proof.findings


def test_stamp_is_idempotent():
    once = attest.stamp(DRAFT)
    twice = attest.stamp(once)
    assert attest.content_digest(once) == attest.content_digest(twice)
    assert attest.verify(twice).verdict is Verdict.VERIFIED


def test_editing_content_after_stamping_is_refuted():
    stamped = attest.stamp(DRAFT)
    edited = stamped.replace("God class", "God object")
    proof = attest.verify(edited)
    assert proof.verdict is Verdict.REFUTED


def test_editing_only_the_attestation_block_stays_verified():
    """The original bug: writing the digest must not invalidate it."""
    stamped = attest.stamp(DRAFT)
    reannotated = stamped.replace("sha256:", "reviewed-by: alice\nsha256:")
    assert attest.verify(reannotated).verdict is Verdict.VERIFIED


def test_whole_file_hashing_would_have_broken():
    """Guard the regression: naive whole-file hashing IS unstable here."""
    stamped = attest.stamp(DRAFT)
    naive_before = attest.digest(DRAFT.encode())
    naive_after = attest.digest(stamped.encode())
    assert naive_before != naive_after, "whole-file hashing should have drifted"
    # The scoped digest is what stays stable.
    assert attest.content_digest(stamped) == attest.content_digest(DRAFT)


def test_unstamped_document_is_unobservable_not_verified():
    proof = attest.verify(DRAFT)
    assert proof.verdict is Verdict.UNOBSERVABLE
    assert not proof.ok()


def test_expected_digest_is_compared_directly():
    good = attest.content_digest(DRAFT)
    assert attest.verify(DRAFT, good).verdict is Verdict.VERIFIED
    assert attest.verify(DRAFT, "0" * 64).verdict is Verdict.REFUTED


# --------------------------------------------------------------------------- #
# closure: evidence that is green but not in force
# --------------------------------------------------------------------------- #


def test_unmerged_evidence_refutes():
    claims = [
        closure.Claim("witness", [closure.Evidence("abc1234", merged=False, kind="branch")]),
    ]
    proof = closure.check_closure(claims)
    assert proof.verdict is Verdict.REFUTED
    assert "not merged" in proof.findings[0]


def test_merged_evidence_verifies():
    claims = [
        closure.Claim("witness", [closure.Evidence("abc1234", merged=True)]),
    ]
    assert closure.check_closure(claims).verdict is Verdict.VERIFIED


def test_claim_without_evidence_is_unobservable():
    proof = closure.check_closure([closure.Claim("witness", [])])
    assert proof.verdict is Verdict.UNOBSERVABLE
    assert not proof.ok()


def test_empty_claim_set_proves_nothing():
    proof = closure.check_closure([])
    assert proof.verdict is Verdict.UNOBSERVABLE


def test_unpinned_ref_is_reported_as_dangling():
    claims = [
        closure.Claim("witness", [closure.Evidence("main", merged=True, kind="commit")]),
    ]
    proof = closure.check_closure(claims)
    assert proof.verdict is Verdict.UNOBSERVABLE
    assert any("not a pinned object id" in f for f in proof.findings)


def test_merged_commits_returns_only_the_safe_subset():
    claims = [
        closure.Claim(
            "witness",
            [
                closure.Evidence("aaa1111", merged=True),
                closure.Evidence("bbb2222", merged=False),
            ],
        )
    ]
    assert closure.merged_commits(claims) == {"witness": ["aaa1111"]}


def test_require_merged_false_downgrades_to_report():
    claims = [closure.Claim("w", [closure.Evidence("abc1234", merged=False)])]
    assert closure.check_closure(claims, require_merged=False).verdict is Verdict.VERIFIED


# --------------------------------------------------------------------------- #
# phases: consume before verify
# --------------------------------------------------------------------------- #


def test_correct_ordering_verifies():
    proof = phases.check_phases(
        [("produce", "a"), ("verify", "a"), ("consume", "a")]
    )
    assert proof.verdict is Verdict.VERIFIED


def test_consume_without_verify_is_refuted():
    proof = phases.check_phases([("produce", "a"), ("consume", "a")])
    assert proof.verdict is Verdict.REFUTED
    assert phases.unverified_consumers([("produce", "a"), ("consume", "a")]) == ["a"]


def test_out_of_order_is_refuted():
    proof = phases.check_phases([("consume", "a"), ("produce", "a"), ("verify", "a")])
    assert proof.verdict is Verdict.REFUTED
    assert any("out of order" in f for f in proof.findings)


def test_unknown_operation_is_unobservable():
    proof = phases.check_phases([("produce", "a"), ("teleport", "a")])
    assert proof.verdict is Verdict.UNOBSERVABLE
    assert not proof.ok()


def test_empty_trace_is_unobservable():
    assert phases.check_phases([]).verdict is Verdict.UNOBSERVABLE


# --------------------------------------------------------------------------- #
# idempotency: replay divergence
# --------------------------------------------------------------------------- #


def test_stable_replay_verifies():
    ops = idempotency.set_ops([("mem:a", 1), ("mem:a", 1)])
    assert idempotency.check_idempotent(ops, {}).verdict is Verdict.VERIFIED


def test_non_deterministic_replay_is_refuted():
    """An op that reads something outside its state diverges across replays."""
    tick = iter(range(100))

    def leaky(state):
        state["seen"] = next(tick)
        return state

    proof = idempotency.check_idempotent([leaky], {}, runs=3)
    assert proof.verdict is Verdict.REFUTED
    assert "distinct states" in proof.findings[0]


def test_raising_operation_is_refuted_not_crashed():
    def boom(state):
        raise RuntimeError("store unavailable")

    proof = idempotency.check_idempotent([boom], {})
    assert proof.verdict is Verdict.REFUTED
    assert any("RuntimeError" in f for f in proof.findings)


def test_idempotent_sequence_passes_the_once_check():
    ops = idempotency.set_ops([("mem:a", 1)])
    assert idempotency.check_idempotent_once(ops, {}).verdict is Verdict.VERIFIED


def test_accumulating_sequence_fails_the_once_check():
    """The real retry hazard: an op that accumulates turns a retry into a duplicate."""

    def counting(state):
        state["n"] = state.get("n", 0) + 1
        return state

    # Deterministic, but not idempotent -- exactly the case worth catching.
    assert idempotency.check_idempotent([counting], {}).verdict is Verdict.VERIFIED
    proof = idempotency.check_idempotent_once([counting], {})
    assert proof.verdict is Verdict.REFUTED
    assert "twice does not equal" in proof.findings[0]


def test_single_run_cannot_prove_determinism():
    assert idempotency.check_idempotent([], {}, runs=1).verdict is Verdict.UNOBSERVABLE


def test_empty_operation_set_is_unobservable():
    assert idempotency.check_idempotent([], {}).verdict is Verdict.UNOBSERVABLE


def test_fingerprint_is_key_order_independent():
    assert idempotency.fingerprint({"a": 1, "b": 2}) == idempotency.fingerprint({"b": 2, "a": 1})


def test_initial_state_is_not_mutated():
    initial = {"keep": "me"}
    idempotency.replay(idempotency.set_ops([("x", 1)]), initial)
    assert initial == {"keep": "me"}


# --------------------------------------------------------------------------- #
# the invariant that matters most
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "proof",
    [
        attest.verify(DRAFT),
        closure.check_closure([]),
        closure.check_closure([closure.Claim("x", [])]),
        phases.check_phases([]),
        phases.check_phases([("teleport", "a")]),
        idempotency.check_idempotent([], {}),
        idempotency.check_idempotent([], {}, runs=1),
    ],
)
def test_unobservable_never_reads_as_a_pass(proof):
    """Collapsing 'cannot tell' into False is how unverifiable claims get trusted."""
    assert proof.verdict is Verdict.UNOBSERVABLE
    assert proof.ok() is False
    assert proof.verdict.gateable() is False
