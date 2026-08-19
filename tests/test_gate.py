"""Scientific claim gate: the ten checks lower claim strength on failure."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import ScientificClaimGate  # noqa: E402


def test_all_checks_pass_is_strong():
    gate = ScientificClaimGate()
    a = gate.check(claim="x", n_samples=61, matched=True, coverage="full",
                   cross_validated=True)
    assert a.strength == "STRONG"


def test_pooled_correlation_lowers_to_weak():
    gate = ScientificClaimGate()
    a = gate.check(claim="pooled correlation claim", n_samples=61,
                   matched=False, coverage="partial", confounding_free=False)
    assert a.strength == "WEAK"
    assert "confounding" in [c.name for c in a.failed()]


def test_small_sample_is_weak():
    gate = ScientificClaimGate(min_sample=5)
    a = gate.check(claim="x", n_samples=3, matched=True, coverage="full")
    assert a.strength == "WEAK"
    assert "sample_size" in [c.name for c in a.failed()]


def test_adjusted_claim_qualifies():
    gate = ScientificClaimGate()
    a = gate.check(claim="x", n_samples=6, matched=True, coverage="partial",
                   cross_validated=False)
    adjusted = gate.adjusted_claim("The trend holds.", a)
    assert a.strength in ("MODERATE", "WEAK")
    assert "MODERATE" in adjusted or "WEAK" in adjusted


if __name__ == "__main__":
    test_all_checks_pass_is_strong()
    test_pooled_correlation_lowers_to_weak()
    test_small_sample_is_weak()
    test_adjusted_claim_qualifies()
    print("claim gate OK")
