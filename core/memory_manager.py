"""Central memory store (v0.1.2).

MemoryStore is a FACADE: it owns the durable file layout, delegates every
write to `core/storage` (atomic), every transition decision to
`core/transition_policy` (single source of truth), and the claim model to
`core/models`. No business rule is duplicated here.

Safety invariants (same transition policy for claims AND decisions):
  * an UNREVIEWED conflicting claim/decision can NEVER change an ACCEPTED one;
  * auto-accept requires registry-resolved canonical source + HIGH confidence
    + no conflict (filename heuristics never grant write authority);
  * superseding happens ONLY through explicit review (`accept_change` /
    `accept_decision`), each carrying reviewed_by / reviewed_at and full
    contradiction provenance;
  * claim/change ids are STABLE (never array indices, never regenerated).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time

import yaml

from . import storage
from . import transition_policy as policy
from .provenance import new_id, now_iso, now_date, MemoryProvenanceError

DEFAULT_ACCEPT_CONFIDENCE = "HIGH"

# The durable memory allowlist restored by rollback (P1-12).
DURABLE_MEMORY_FILES = [
    "PROJECT_MEMORY.md", "SCIENTIFIC_STATE.yaml", "DECISION_LEDGER.jsonl",
    "LESSON_MEMORY.jsonl", "OPEN_QUESTIONS.yaml", "DATA_REGISTRY.json",
    "METHOD_REGISTRY.yaml",
]

# Durable-memory paths (relative to a snapshot/pre-rollback directory).
_MEMORY_KEYS = {
    "project_memory": "PROJECT_MEMORY.md",
    "scientific_state": "SCIENTIFIC_STATE.yaml",
    "decision_ledger": "DECISION_LEDGER.jsonl",
    "lesson_memory": "LESSON_MEMORY.jsonl",
    "open_questions": "OPEN_QUESTIONS.yaml",
    "data_registry": "DATA_REGISTRY.json",
    "method_registry": "METHOD_REGISTRY.yaml",
}


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{digest}"


class MemoryError(RuntimeError):
    pass


class MemoryStore:
    """File-backed long-term memory for one research project."""

    def __init__(self, root: str, active_profile: str | None = None,
                 project_id: str | None = None) -> None:
        self.root = os.path.abspath(root)
        self.memory_dir = os.path.join(self.root, "memory")
        self.cases_dir = os.path.join(self.root, "cases")
        self.skills_dir = os.path.join(self.root, "skills")
        self.core_skills_dir = os.path.join(self.skills_dir, "core")
        self.profiles_dir = os.path.join(self.root, "profiles")
        self.reflections_dir = os.path.join(self.root, "reflections")
        self.snapshots_dir = os.path.join(self.root, "snapshots")
        self.outputs_dir = os.path.join(self.root, "outputs")
        self.project_id = project_id
        self.active_profile = active_profile or self._read_active_profile()

        self.project_memory_path = os.path.join(self.memory_dir, "PROJECT_MEMORY.md")
        self.scientific_state_path = os.path.join(self.memory_dir, "SCIENTIFIC_STATE.yaml")
        self.decision_ledger_path = os.path.join(self.memory_dir, "DECISION_LEDGER.jsonl")
        self.lesson_memory_path = os.path.join(self.memory_dir, "LESSON_MEMORY.jsonl")
        self.open_questions_path = os.path.join(self.memory_dir, "OPEN_QUESTIONS.yaml")
        self.data_registry_path = os.path.join(self.memory_dir, "DATA_REGISTRY.json")
        self.method_registry_path = os.path.join(self.memory_dir, "METHOD_REGISTRY.yaml")

    # ------------------------------------------------------------------ profile
    def _read_active_profile(self) -> str | None:
        marker = os.path.join(self.root, ".active_profile")
        if os.path.exists(marker):
            value = self._read_text(marker).strip()
            return value or None
        return None

    def set_active_profile(self, profile: str | None) -> None:
        """Persist the project configuration that decides which profile's
        skills the Retriever may index (P0-9: decided by config, never by
        query keywords)."""
        self.active_profile = profile
        marker = os.path.join(self.root, ".active_profile")
        storage.atomic_write_text(marker, (profile or "") + "\n")

    @property
    def profile_skills_dir(self) -> str | None:
        if not self.active_profile:
            return None
        return os.path.join(self.profiles_dir, self.active_profile, "skills")

    # ------------------------------------------------------------------ paths
    def ensure_layout(self) -> None:
        for d in (self.memory_dir, self.cases_dir,
                  os.path.join(self.cases_dir, "successes"),
                  os.path.join(self.cases_dir, "failures"),
                  self.skills_dir, self.core_skills_dir,
                  os.path.join(self.reflections_dir, "task"),
                  os.path.join(self.reflections_dir, "milestone"),
                  self.snapshots_dir, self.outputs_dir,
                  os.path.join(self.profiles_dir, ".keep")):
            os.makedirs(d, exist_ok=True)

    # ------------------------------------------------------------------ io (storage-backed)
    def _read_text(self, path: str, default: str = "") -> str:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()

    def _read_yaml(self, path: str, default):
        try:
            return yaml.safe_load(self._read_text(path)) or default
        except yaml.YAMLError as exc:
            raise MemoryError(f"corrupt YAML {path}: {exc}") from exc

    def _write_yaml(self, path: str, data) -> None:
        storage.atomic_write_yaml(path, data)

    def _read_json(self, path: str, default):
        try:
            return json.loads(self._read_text(path, "{}")) if os.path.exists(path) else default
        except json.JSONDecodeError as exc:
            raise MemoryError(f"corrupt JSON {path}: {exc}") from exc

    def _write_json(self, path: str, data) -> None:
        storage.atomic_write_json(path, data)

    def _read_jsonl(self, path: str) -> list[dict]:
        rows = []
        if not os.path.exists(path):
            return rows
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows

    def _append_jsonl(self, path: str, row: dict) -> None:
        storage.append_jsonl(path, row)

    def _rewrite_jsonl(self, path: str, rows: list[dict]) -> None:
        storage.atomic_rewrite_jsonl(path, rows)

    # ------------------------------------------------------------------ state accessors
    def project_memory(self) -> str:
        return self._read_text(self.project_memory_path)

    def scientific_state(self) -> dict:
        return self._migrate_v011_claims(self._read_yaml(self.scientific_state_path, {}))

    def decisions(self) -> list[dict]:
        return self._read_jsonl(self.decision_ledger_path)

    def lessons(self) -> list[dict]:
        return self._migrate_lessons(self._read_jsonl(self.lesson_memory_path))

    def open_questions(self) -> dict:
        return self._read_yaml(self.open_questions_path, {})

    def data_registry(self) -> dict:
        return self._read_json(self.data_registry_path, {})

    def method_registry(self) -> dict:
        return self._read_yaml(self.method_registry_path, {})

    # ------------------------------------------------------------------ initialization
    def is_initialized(self) -> bool:
        """Explicit-schema initialization check (P0-1). `meta.initialized`
        must be true; legacy files WITHOUT a `meta` key count as initialized
        only when they actually carry project content (never a template)."""
        state = self.scientific_state()
        meta = state.get("meta") or {}
        if meta.get("initialized") is True:
            return True
        if "meta" not in state:
            return bool(state.get("project") or state.get("current_conclusions"))
        return False

    def mark_initialized(self, reviewer: str = "human") -> dict:
        state = self.scientific_state()
        meta = dict(state.get("meta") or {})
        meta["initialized"] = True
        meta["initialized_at"] = now_iso()
        meta["initialized_by"] = reviewer
        state["meta"] = meta
        self._write_yaml(self.scientific_state_path, state)
        return meta

    # ------------------------------------------------------------------ seed
    def seed(self) -> None:
        """Write valid empty-state skeleton files for MISSING or EMPTY files.
        Idempotent; never overwrites non-empty content. The runtime memory
        contains NO placeholder/fake records (P0-1)."""
        self.ensure_layout()
        if not os.path.exists(self.data_registry_path) or not self._read_text(self.data_registry_path).strip():
            self._write_json(self.data_registry_path, {"datasets": []})
        if not os.path.exists(self.scientific_state_path) or not self._read_text(self.scientific_state_path).strip():
            self._write_yaml(self.scientific_state_path, self._empty_state())
        if not os.path.exists(self.open_questions_path) or not self._read_text(self.open_questions_path).strip():
            self._write_yaml(self.open_questions_path,
                             {"questions": [], "blockers": [], "next_step_owners": []})
        if not os.path.exists(self.method_registry_path) or not self._read_text(self.method_registry_path).strip():
            self._write_yaml(self.method_registry_path, {"methods": []})
        for path in (self.project_memory_path, self.decision_ledger_path,
                     self.lesson_memory_path):
            if not os.path.exists(path):
                storage.atomic_write_text(path, "")

    def _empty_state(self) -> dict:
        return {
            "meta": {"initialized": False},
            "project": None,
            "system": None,
            "current_stage": None,
            "canonical_datasets": {},
            "frozen_definitions": {},
            "current_conclusions": {},
            "rejected_results": {},
            "superseded_results": [],
            "blockers": [],
            "next_steps": [],
            "pending_changes": [],
        }

    # ------------------------------------------------------------------ project memory
    def write_project_memory(self, text: str) -> None:
        storage.atomic_write_text(self.project_memory_path, text)

    # ------------------------------------------------------------------ claims (scientific state)
    def _as_claim(self, topic: str, val, *, migrated: bool = False,
                  status: str | None = None) -> dict:
        if isinstance(val, dict) and ("value" in val or "source" in val or "claim_id" in val):
            rec = dict(val)
            rec.setdefault("claim_id",
                           rec.get("claim_id") or _stable_id("claim", topic))
            rec.setdefault("topic", topic)
            rec.setdefault("value", val.get("value", ""))
            rec.setdefault("source", val.get("source", ""))
            rec.setdefault("date", val.get("date", ""))
            rec.setdefault("status", status or val.get("status", "ACCEPTED"))
            rec.setdefault("confidence", val.get("confidence", "MEDIUM"))
            if migrated:
                rec.setdefault("migrated", True)
            return rec
        return {
            "claim_id": _stable_id("claim", topic),
            "topic": topic,
            "value": val,
            "source": "",
            "date": "",
            "status": status or "ACCEPTED",
            "confidence": "MEDIUM",
            "migrated": True,
        }

    def _migrate_v011_claims(self, state: dict) -> dict:
        """v0.1.1 -> v0.1.2 schema migration, applied on READ.

        * primitive `topic: value` and `topic: {value, source, ...}` claims
          become ClaimRecords with stable claim_ids;
        * the legacy `accepted_results` bucket folds into
          `current_conclusions` (one claim model);
        * pending changes without a change_id get a stable one.
        Writes always persist the normalized form.
        """
        claims: dict[str, dict] = {}
        for bucket in ("current_conclusions", "accepted_results"):
            table = state.get(bucket)
            if isinstance(table, dict):
                for topic, val in table.items():
                    claims[topic] = self._as_claim(topic, val, migrated=True)
        state["current_conclusions"] = claims
        state.pop("accepted_results", None)

        superseded = []
        for item in state.get("superseded_results", []) or []:
            if isinstance(item, dict):
                superseded.append(
                    self._as_claim(item.get("topic", "?"), item,
                                   migrated=True, status="SUPERSEDED"))
        state["superseded_results"] = superseded

        rejected = {}
        for topic, val in (state.get("rejected_results", {}) or {}).items():
            rejected[topic] = self._as_claim(topic, val, migrated=True,
                                             status="REJECTED")
        state["rejected_results"] = rejected

        for pc in state.get("pending_changes", []) or []:
            if not pc.get("change_id"):
                pc["change_id"] = _stable_id(
                    "change", pc.get("topic", ""), pc.get("value", ""),
                    pc.get("source", ""))
        return state

    def _find_existing_claim(self, state: dict, topic: str) -> dict | None:
        return state.get("current_conclusions", {}).get(topic)

    def update_scientific_state(self, changes: dict, *,
                                source: str, auto_commit: bool = True,
                                confidence: str = DEFAULT_ACCEPT_CONFIDENCE,
                                date: str | None = None) -> dict[str, dict]:
        """Apply new claims under the unified transition policy (P0-3/P0-4).

        Returns {topic: outcome} where outcome is either an accepted
        ClaimRecord (status ACCEPTED) or a PendingChange (status CANDIDATE,
        requires_review=True). An unreviewed conflicting claim NEVER changes
        an existing ACCEPTED claim.
        """
        confidence = policy.validate_confidence(confidence)
        state = self.scientific_state()
        datasets = self.data_registry().get("datasets", [])
        verdict = policy.canonical_authority(datasets, source)
        outcomes: dict[str, dict] = {}
        for topic, value in changes.items():
            old = self._find_existing_claim(state, topic)
            conflict = (old is not None
                        and policy.classify_conflict(old.get("value"), value,
                                                     old.get("status")))
            eligible = policy.can_auto_accept_claim(
                canonical=verdict.canonical, confidence=confidence,
                auto_commit=auto_commit, conflict=conflict)
            if eligible:
                claim_id = old["claim_id"] if old is not None else new_id("claim")
                claim = {
                    "claim_id": claim_id,
                    "topic": topic,
                    "value": value,
                    "source": source,
                    "date": date or now_date(),
                    "status": "ACCEPTED",
                    "confidence": confidence,
                }
                state["current_conclusions"][topic] = claim
                outcomes[topic] = claim
            else:
                change = {
                    "change_id": new_id("change"),
                    "topic": topic,
                    "value": value,
                    "source": source,
                    "date": date or now_date(),
                    "status": "CANDIDATE",
                    "confidence": confidence,
                    "requires_review": True,
                    "conflicts": [topic] if conflict else [],
                }
                state.setdefault("pending_changes", []).append(change)
                outcomes[topic] = change
        self._write_yaml(self.scientific_state_path, state)
        return outcomes

    def accept_change(self, change_id: str, *, reviewer: str) -> dict:
        """Explicit reviewer approval for one pending claim change (P0-3).

        Only here may a conflicting new claim supersede an ACCEPTED one:
        new CANDIDATE -> ACCEPTED, conflicting old ACCEPTED -> SUPERSEDED
        (moved to superseded_results with superseded_by), full contradiction
        provenance recorded. change_id is stable and never an array index.
        """
        state = self.scientific_state()
        pending = state.get("pending_changes", [])
        target = next((pc for pc in pending if pc.get("change_id") == change_id), None)
        if target is None:
            raise MemoryError(f"pending change {change_id} not found")
        claim_id = _stable_id("claim", target.get("topic", ""),
                              str(target.get("value", "")), change_id)
        contradictions = []
        old = self._find_existing_claim(state, target.get("topic", "?"))
        if old is not None and str(old.get("value")) != str(target.get("value")):
            old["status"] = "SUPERSEDED"
            old["superseded_by"] = claim_id
            state.setdefault("superseded_results", []).append(old)
            contradictions.append({
                "kind": "CONTRADICTION",
                "conflicting_claim_id": old.get("claim_id"),
                "old_value": old.get("value"),
                "new_value": target.get("value"),
                "source": target.get("source"),
                "confidence": target.get("confidence"),
                "old_status": "ACCEPTED",
                "prior_after": "SUPERSEDED",
                "new_status": "ACCEPTED",
                "requires_review": False,
                "reviewed_by": reviewer,
                "note": "reviewer approved; conflicting accepted claim superseded",
            })
        claim = {
            "claim_id": claim_id,
            "topic": target.get("topic", "?"),
            "value": target.get("value"),
            "source": target.get("source", ""),
            "date": target.get("date", now_date()),
            "status": "ACCEPTED",
            "confidence": target.get("confidence", "MEDIUM"),
            "reviewed_by": reviewer,
            "reviewed_at": now_iso(),
            "contradictions": contradictions,
        }
        state["current_conclusions"][claim["topic"]] = claim
        state["pending_changes"] = [pc for pc in pending if pc.get("change_id") != change_id]
        self._write_yaml(self.scientific_state_path, state)
        return claim

    # ------------------------------------------------------------------ decisions
    def add_decision(self, *, topic: str, decision: str, reason: str,
                     source: str, alternatives: list[str] | None = None,
                     evidence: str | None = None,
                     confidence: str = "MEDIUM",
                     status: str = "CANDIDATE",
                     decision_id: str | None = None,
                     timestamp: str | None = None,
                     detect_contradictions: bool = True) -> dict:
        """Record a decision under the unified transition policy (P0-6).

        The default status is CANDIDATE. `status="ACCEPTED"` is honored ONLY
        when the policy allows it (registry-resolved canonical source + HIGH
        confidence + no conflict); otherwise the entry is forced to CANDIDATE
        with requires_review=True. A conflicting decision can never change an
        existing ACCEPTED decision.
        """
        confidence = policy.validate_confidence(confidence)
        entry = {
            "decision_id": decision_id or new_id("decision"),
            "timestamp": timestamp or now_iso(),
            "topic": topic,
            "decision": decision,
            "alternatives": alternatives or [],
            "reason": reason,
            "evidence": evidence or "",
            "source": source,
            "confidence": confidence,
            "status": status,
        }
        conflict = False
        if detect_contradictions:
            contradictions, conflict = policy.decision_conflicts(
                self.decisions(), entry)
            if contradictions:
                entry["contradictions"] = contradictions
                # a conflict with an ACCEPTED prior forces CANDIDATE + review
                # regardless of the requested status (same rule as claims)
                if any(c.get("old_status") == "ACCEPTED"
                       for c in contradictions):
                    entry["status"] = "CANDIDATE"
                    entry["requires_review"] = True
        if status == "ACCEPTED":
            verdict = policy.canonical_authority(
                self.data_registry().get("datasets", []), source)
            if not policy.can_auto_accept_decision(
                    canonical=verdict.canonical, confidence=confidence,
                    conflict=conflict):
                entry["status"] = "CANDIDATE"
                entry["requires_review"] = True
        self._append_jsonl(self.decision_ledger_path, entry)
        return entry

    def import_accepted_decision(self, *, topic: str, decision: str, reason: str,
                                 source: str, reviewer: str,
                                 alternatives: list[str] | None = None,
                                 evidence: str | None = None,
                                 confidence: str = "HIGH",
                                 decision_id: str | None = None,
                                 timestamp: str | None = None) -> dict:
        """Explicit migration/import path for already-human-confirmed history
        (P0-6). There is no generic `trusted=True` escape hatch; the reviewer
        identity is mandatory and recorded."""
        entry = {
            "decision_id": decision_id or new_id("decision"),
            "timestamp": timestamp or now_iso(),
            "topic": topic,
            "decision": decision,
            "alternatives": alternatives or [],
            "reason": reason,
            "evidence": evidence or "",
            "source": source,
            "confidence": policy.validate_confidence(confidence),
            "status": "ACCEPTED",
            "reviewed_by": reviewer,
            "reviewed_at": now_iso(),
            "requires_review": False,
            "imported": True,
        }
        self._append_jsonl(self.decision_ledger_path, entry)
        return entry

    def accept_decision(self, decision_id: str, *, reviewer: str) -> dict:
        """Explicit reviewer-approval path for decisions (unchanged semantics
        from v0.1.1; kept as the single supersede path)."""
        rows = self.decisions()
        target = next((r for r in rows if r.get("decision_id") == decision_id), None)
        if target is None:
            raise MemoryError(f"decision {decision_id} not found")
        if target.get("status") == "ACCEPTED":
            target["reviewed_by"] = reviewer
            target["reviewed_at"] = now_iso()
            self._rewrite_jsonl(self.decision_ledger_path, rows)
            return target
        dirty = False
        for prior in rows:
            if prior is target or prior.get("status") in ("SUPERSEDED", "REJECTED"):
                continue
            if (prior.get("topic") == target.get("topic")
                    and prior.get("decision") != target.get("decision")):
                prior_status = prior.get("status")
                prior["status"] = "SUPERSEDED"
                prior["superseded_by"] = decision_id
                dirty = True
                target.setdefault("contradictions", []).append({
                    "kind": "CONTRADICTION",
                    "conflicting_decision_id": prior["decision_id"],
                    "old_decision": prior["decision"],
                    "new_decision": target["decision"],
                    "source": target["source"],
                    "confidence": target["confidence"],
                    "old_status": prior_status,
                    "prior_after": "SUPERSEDED",
                    "new_status": "ACCEPTED",
                    "requires_review": False,
                    "reviewed_by": reviewer,
                    "note": "reviewer approved; prior accepted decision superseded "
                            "with full history retained",
                })
        target["status"] = "ACCEPTED"
        target["requires_review"] = False
        target["reviewed_by"] = reviewer
        target["reviewed_at"] = now_iso()
        self._rewrite_jsonl(self.decision_ledger_path, rows)
        return target

    # ------------------------------------------------------------------ lessons
    def _migrate_lessons(self, lessons: list[dict]) -> list[dict]:
        """Synthesize VerificationRecords for legacy lessons that carry only a
        times_verified integer, so promotion counts come from distinct
        verification identities (P0-7)."""
        for lesson in lessons:
            verifications = lesson.get("verifications")
            if not verifications and lesson.get("times_verified", 0) > 0:
                lesson["verifications"] = [
                    {"verification_id": new_id("verif"),
                     "source": lesson.get("source", ""),
                     "task_id": f"legacy-{i}",
                     "date": lesson.get("date", ""),
                     "confirmation": "legacy verification (pre-v0.1.2)"}
                    for i in range(int(lesson.get("times_verified", 0)))
                ]
            lesson["times_verified"] = self._unique_verifications(lesson)
        return lessons

    def _unique_verifications(self, lesson: dict) -> int:
        seen = set()
        for v in lesson.get("verifications", []):
            seen.add((v.get("source"), v.get("task_id")))
        return len(seen)

    def add_lesson(self, *, trigger: str, failure: str, root_cause: str,
                   fix: str, generalizable_rule: str, scope: str,
                   source: str, confidence: str = "MEDIUM",
                   status: str = "CANDIDATE") -> dict:
        entry = {
            "lesson_id": new_id("lesson"),
            "trigger": trigger,
            "failure": failure,
            "root_cause": root_cause,
            "fix": fix,
            "generalizable_rule": generalizable_rule,
            "scope": scope,
            "confidence": policy.validate_confidence(confidence),
            "times_verified": 0,
            "status": status,
            "source": source,
            "date": now_date(),
            "verifications": [],
        }
        self._append_jsonl(self.lesson_memory_path, entry)
        return entry

    def verify_lesson(self, lesson_id: str, *, source: str,
                      task_id: str | None = None,
                      confirmation: str = "") -> dict:
        """Independent verification (P0-7). An exact duplicate
        (source, task_id) is NOT counted a second time;
        `times_verified = len(unique (source, task_id) verifications)`."""
        lessons = self.lessons()
        for lesson in lessons:
            if lesson["lesson_id"] == lesson_id:
                verifications = lesson.setdefault("verifications", [])
                duplicate = any(v.get("source") == source and v.get("task_id") == task_id
                                for v in verifications)
                if not duplicate:
                    verifications.append({
                        "verification_id": new_id("verif"),
                        "source": source,
                        "task_id": task_id,
                        "date": now_date(),
                        "confirmation": confirmation,
                    })
                lesson["times_verified"] = self._unique_verifications(lesson)
                lesson["status"] = "VERIFIED" if lesson["times_verified"] >= 1 \
                    else lesson.get("status", "CANDIDATE")
                self._rewrite_jsonl(self.lesson_memory_path, lessons)
                return lesson
        raise MemoryError(f"lesson {lesson_id} not found")

    def find_lessons(self, status: str | None = None) -> list[dict]:
        lessons = self.lessons()
        return [l for l in lessons if status is None or l.get("status") == status]

    def mark_lesson_promoted(self, lesson_id: str, skill_name: str) -> dict:
        """Mark one lesson PROMOTED after the skill file was written (P0-8)."""
        lessons = self.lessons()
        for lesson in lessons:
            if lesson["lesson_id"] == lesson_id:
                lesson["status"] = "PROMOTED"
                lesson["promoted_to"] = skill_name
                lesson["promoted_at"] = now_date()
                self._rewrite_jsonl(self.lesson_memory_path, lessons)
                return lesson
        raise MemoryError(f"lesson {lesson_id} not found")

    def distinct_verifications(self, lesson_id: str) -> int:
        for lesson in self.lessons():
            if lesson["lesson_id"] == lesson_id:
                return self._unique_verifications(lesson)
        return 0

    # ------------------------------------------------------------------ canonical authority (public)
    def is_canonical_source(self, source: str) -> bool:
        """Public, registry-authoritative check (P0-5). Used for display and
        read-only classification; WRITE authorization goes through
        `can_auto_accept` (policy)."""
        return policy.canonical_authority(
            self.data_registry().get("datasets", []), source).canonical

    def can_auto_accept(self, source: str, confidence: str,
                        conflict: bool = False) -> bool:
        """The single auto-accept gate shared by reflection and the CLI."""
        verdict = policy.canonical_authority(
            self.data_registry().get("datasets", []), source)
        return policy.can_auto_accept_claim(
            canonical=verdict.canonical,
            confidence=policy.validate_confidence(confidence),
            auto_commit=True, conflict=conflict)

    # ------------------------------------------------------------------ registries
    def register_dataset(self, *, dataset_id: str, name: str, path: str,
                         version: str, status: str, scope: str,
                         rows: int, columns: list[str], definition: str,
                         source: str, supersedes: str | None = None,
                         superseded_by: str | None = None) -> dict:
        reg = self.data_registry()
        reg["datasets"] = reg.get("datasets", [])
        status = status.upper()
        if status in policy.NON_CANONICAL_STATUSES | policy.CANONICAL_STATUSES:
            pass
        else:
            raise MemoryError(f"unrecognized dataset status {status!r}")
        entry = {
            "dataset_id": dataset_id, "name": name, "path": path,
            "version": version, "status": status, "scope": scope,
            "rows": rows, "columns": columns, "definition": definition,
            "source": source, "created_at": now_iso(),
            "supersedes": supersedes, "superseded_by": superseded_by,
        }
        for existing in reg["datasets"]:
            if existing["dataset_id"] == dataset_id:
                raise MemoryError(f"dataset {dataset_id} already registered")
        reg["datasets"].append(entry)
        self._write_json(self.data_registry_path, reg)
        return entry

    def register_method(self, *, method: str, version: str, settings: dict,
                        notes: str = "", source: str = "") -> dict:
        reg = self.method_registry()
        reg["methods"] = reg.get("methods", [])
        entry = {
            "method": method, "version": version, "settings": settings,
            "notes": notes, "source": source, "registered_at": now_iso(),
        }
        reg["methods"].append(entry)
        self._write_yaml(self.method_registry_path, reg)
        return entry

    def set_open_questions(self, questions: dict) -> None:
        self._write_yaml(self.open_questions_path, questions)

    # ------------------------------------------------------------------ snapshot / rollback
    def snapshot(self, milestone: str) -> str:
        date = now_date()
        target = os.path.join(self.snapshots_dir, f"{date}_{milestone}")
        os.makedirs(target, exist_ok=True)
        for fname in DURABLE_MEMORY_FILES:
            src = os.path.join(self.memory_dir, fname)
            if os.path.isfile(src):
                storage.atomic_write_text(os.path.join(target, fname),
                                          self._read_text(src))
        return target

    def rollback(self, snapshot_dir: str) -> str:
        """Transactionally restore a snapshot that lives INSIDE
        store.snapshots_dir only (P1-12).

        rollback is all-or-nothing: a pre-rollback snapshot of the CURRENT
        durable memory is taken first, every restore payload is read into
        memory BEFORE any write, and if any single write fails the ENTIRE
        durable memory is restored from the pre-rollback snapshot — so a
        failed rollback can never leave a half-applied mix of old and new
        files. If restoring the pre-rollback state itself fails, a
        catastrophic error is raised (never swallowed).
        """
        snap = os.path.abspath(snapshot_dir)
        snap_base = os.path.abspath(self.snapshots_dir)
        if os.path.commonpath([snap, snap_base]) != snap_base or not os.path.isdir(snap):
            raise MemoryError(f"rollback source must be inside {self.snapshots_dir}")
        # 1. pre-rollback snapshot of the current durable memory
        pre = self.snapshot(f"pre_rollback_{int(time.time())}")
        # 2+3. validate + read ALL restore payloads into memory before any write
        restore_payloads: dict[str, str] = {}
        for fname in DURABLE_MEMORY_FILES:
            src = os.path.join(snap, fname)
            if not os.path.isfile(src):
                continue
            try:
                restore_payloads[fname] = self._read_text(src)
            except OSError as exc:
                raise MemoryError(
                    f"cannot read rollback payload {src}: {exc}") from exc
        # 4. atomic replace one durable file at a time
        for fname, payload in restore_payloads.items():
            try:
                storage.atomic_write_text(os.path.join(self.memory_dir, fname),
                                          payload)
            except OSError as exc:
                # 5. any failure -> restore the ENTIRE pre-rollback state
                #    (files written earlier in this loop are covered too)
                self._restore_pre_rollback(pre, exc)
        return snap

    def _restore_pre_rollback(self, pre: str, cause: OSError) -> None:
        """Restore every durable file from the pre-rollback snapshot. Raises a
        catastrophic error if ANY restore itself fails (never half-applied,
        never swallowed)."""
        failures: list[str] = []
        for fname in DURABLE_MEMORY_FILES:
            pre_src = os.path.join(pre, fname)
            if not os.path.isfile(pre_src):
                continue
            try:
                storage.atomic_write_text(os.path.join(self.memory_dir, fname),
                                          self._read_text(pre_src))
            except OSError as restore_exc:
                failures.append(f"{fname}: {restore_exc}")
        if failures:
            raise MemoryError(
                "CATASTROPHIC rollback failure: original restore failed "
                f"({cause}) AND restoring the pre-rollback state failed for: "
                f"{failures}; durable memory may be inconsistent") from cause
        raise MemoryError(
            f"rollback failed mid-restore ({cause}); the pre-rollback state "
            f"was fully restored — durable memory is unchanged") from cause

    def _read_active_profile_marker(self) -> str | None:  # pragma: no cover - small helper
        return self._read_active_profile()
