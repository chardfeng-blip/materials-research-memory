"""Scientific Claim Gate.

Every time a scientific conclusion is about to be output, run the ten checks.
A failed check lowers the allowed claim strength:

    STRONG  -> all checks pass
    MODERATE-> minor gaps
    WEAK    -> major gaps (sample size, no cross-validation, confounding, ...)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ClaimCheck:
    """One claim-gate check result."""
    name: str
    passed: bool
    note: str = ""


@dataclass(frozen=True)
class ClaimAssessment:
    strength: str  # STRONG | MODERATE | WEAK
    checks: list[ClaimCheck] = field(default_factory=list)

    def failed(self) -> list[ClaimCheck]:
        return [c for c in self.checks if not c.passed]

    def summary(self) -> str:
        return (f"claim strength: {self.strength}; "
                f"passed {sum(c.passed for c in self.checks)}/{len(self.checks)} "
                f"checks; failed: {', '.join(c.name for c in self.failed()) or 'none'}")


# The ten mandatory checks (order per project spec §20).
CHECK_NAMES = [
    "sample_size", "matched_design", "data_coverage", "convergence",
    "outlier_sensitivity", "topology_sensitivity", "confounding",
    "cross_validation", "provenance", "method_consistency",
]


class ScientificClaimGate:
    def __init__(self, *, min_sample: int = 5,
                 require_cross_validation: bool = True,
                 require_provenance: bool = True,
                 require_method_consistency: bool = True) -> None:
        self.min_sample = min_sample
        self.require_cross_validation = require_cross_validation
        self.require_provenance = require_provenance
        self.require_method_consistency = require_method_consistency

    def check(self, *, claim: str, n_samples: int,
              matched: bool, coverage: str = "partial",
              converged: bool = True, outliers_handled: bool = True,
              topology_robust: bool = True, confounding_free: bool = True,
              cross_validated: bool = False,
              has_provenance: bool = True,
              method_consistent: bool = True,
              checks: dict[str, bool] | None = None) -> ClaimAssessment:
        """Run all ten checks. `checks` may override individual results."""
        if checks is None:
            checks = {}
        results = {
            "sample_size": n_samples >= self.min_sample,
            "matched_design": matched,
            "data_coverage": coverage == "full",
            "convergence": converged,
            "outlier_sensitivity": outliers_handled,
            "topology_sensitivity": topology_robust,
            "confounding": confounding_free,
            "cross_validation": cross_validated,
            "provenance": has_provenance,
            "method_consistency": method_consistent,
        }
        for key, override in checks.items():
            if key in results:
                results[key] = bool(override)
        check_rows = [ClaimCheck(name, results[name]) for name in CHECK_NAMES]
        failures = [name for name in CHECK_NAMES if not results[name]]
        major = {"sample_size", "confounding", "cross_validation",
                 "method_consistency"}
        if not failures:
            strength = "STRONG"
        elif any(f in major for f in failures):
            strength = "WEAK"
        else:
            strength = "MODERATE"
        return ClaimAssessment(strength=strength, checks=check_rows)

    @staticmethod
    def adjusted_claim(original: str, assessment: ClaimAssessment) -> str:
        """Return the original claim with an appropriate strength qualifier."""
        if assessment.strength == "STRONG":
            return original
        if assessment.strength == "MODERATE":
            return f"{original} [MODERATE confidence — minor gaps: " \
                   f"{', '.join(c.name for c in assessment.failed())}]"
        return f"{original} [WEAK confidence — claims weakened; gaps: " \
               f"{', '.join(c.name for c in assessment.failed())}]"
