"""materials-research-memory core package.

Long-term materials-science research memory for DSH: canonical scientific
state, decision ledger, verified lessons, reusable skills, retrieval,
reflection, and scientific-claim gating.

v0.1.2 structure:
  * `storage`           atomic durable writes + file lock (P1-11)
  * `transition_policy` single source of truth for state transitions (P0-3/5/6)
  * `models`            shared claim/change/verification records (P0-4)
  * `memory_manager`    facade: durable layout + policy + storage
  * `retrieval`         BM25 + generic kind diversification (profile-aware)
  * `reflection` / `lesson_manager` / `skill_promoter` / `project_snapshot`
"""

from .memory_manager import MemoryStore, MemoryError
from .retrieval import Retriever, retrieve_top_k
from .reflection import reflect_task
from .lesson_manager import LessonManager
from .skill_promoter import SkillPromoter
from .provenance import new_id, now_iso, now_date, stamp, ensure_provenance
from .scientific_gate import ScientificClaimGate, ClaimCheck, ClaimAssessment
from .project_snapshot import SnapshotManager
from . import storage, transition_policy, models

__all__ = [
    "MemoryStore", "MemoryError",
    "Retriever", "retrieve_top_k",
    "reflect_task",
    "LessonManager",
    "SkillPromoter",
    "new_id", "now_iso", "now_date", "stamp", "ensure_provenance",
    "ScientificClaimGate", "ClaimCheck", "ClaimAssessment",
    "SnapshotManager",
    "storage", "transition_policy", "models",
]
