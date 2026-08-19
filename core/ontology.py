"""Simple materials-science ontology for tagging and future extension.

Base vocabulary covers generic host-material / species accommodation
domains and is designed to extend to other materials (UO2, W, metals) and
techniques (TEM, EELS, XRD, AIMD) without schema changes.
"""

from __future__ import annotations

ONTOLOGY_BASE = [
    "Material", "Structure", "Defect", "Species", "Calculation",
    "Descriptor", "Energy", "ElectronicProperty", "Transition",
    "Mechanism", "Evidence", "Conclusion",
]

ONTOLOGY_EXTENSIBLE = [
    "UO2", "W", "metal systems", "TEM", "EELS", "XRD", "AIMD",
]

# Synthetic vocabulary used by the hermetic demo fixture (Material-X,
# species A/B/C). The ontology is taggable and extensible: project-specific
# terms are added at runtime via Ontology.add() — nothing project-specific
# is hardcoded here.
SPECIES = ["A", "B", "C", "host"]
DESCRIPTORS = ["Vcav", "Dmin", "Rg", "DR1", "C1", "C2", "Ec", "Hh"]
ENERGY_TERMS = ["formation_energy", "solution_energy", "binding_energy",
                "host_relaxation_energy", "electronic_energy"]


def normalize(term: str) -> str:
    return term.strip().lower()


class Ontology:
    """Taggable vocabulary. `add` allows future extension (UO2/W/TEM/...)."""

    def __init__(self, base: list[str] | None = None,
                 extras: list[str] | None = None) -> None:
        self._terms = {normalize(t) for t in (base or ONTOLOGY_BASE)}
        self._terms.update(normalize(t) for t in (extras or []))

    def add(self, *terms: str) -> None:
        for term in terms:
            self._terms.add(normalize(term))

    def contains(self, term: str) -> bool:
        return normalize(term) in self._terms

    def tags(self, text: str) -> list[str]:
        """Return the ontology terms mentioned in `text` (order of definition)."""
        low = normalize(text)
        found = [t for t in self._terms if t and t in low]
        return found

    def terms(self) -> list[str]:
        return sorted(self._terms)


DEFAULT_ONTOLOGY = Ontology(ONTOLOGY_BASE, ONTOLOGY_EXTENSIBLE)
