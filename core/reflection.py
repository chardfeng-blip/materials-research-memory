"""Task-end reflection.

Generates MEMORY_UPDATE_PROPOSAL.md answering the nine reflection questions,
then applies the auto-commit policy:

  AUTO (write immediately):
    task log, observation, candidate lesson
  REQUIRES_REVIEW (never auto-written):
    accepted scientific conclusion, unless source is a canonical final
    result AND confidence is HIGH AND no conflict exists.
"""

from __future__ import annotations

import datetime
import os

from .memory_manager import MemoryStore
from .provenance import now_iso

REFLECTION_QUESTIONS = [
    "What new fact was established?",
    "What assumption failed?",
    "What decision changed?",
    "What failure occurred?",
    "What fixed it?",
    "Is it reusable?",
    "Did canonical data change?",
    "Was anything superseded?",
    "What remains unresolved?",
]

PROPOSAL_SECTIONS = [
    "NEW_FACTS", "NEW_DECISIONS", "NEW_LESSONS", "POTENTIAL_SKILLS",
    "SUPERSEDED_ITEMS", "OPEN_QUESTIONS",
]


def reflect_task(store: MemoryStore, *, task_id: str, task_summary: str,
                 answers: dict[str, str] | None = None,
                 new_facts: list[dict] | None = None,
                 new_decisions: list[dict] | None = None,
                 new_lessons: list[dict] | None = None,
                 potential_skills: list[str] | None = None,
                 superseded_items: list[dict] | None = None,
                 open_questions: list[str] | None = None,
                 canonical_source: str | None = None,
                 confidence: str = "HIGH",
                 auto_commit: bool = True) -> str:
    """Write a MEMORY_UPDATE_PROPOSAL.md and auto-commit permitted entries.

    Returns the proposal file path.
    """
    answers = answers or {}
    new_facts = new_facts or []
    new_decisions = new_decisions or []
    new_lessons = new_lessons or []
    potential_skills = potential_skills or []
    superseded_items = superseded_items or []
    open_questions = open_questions or []

    store.ensure_layout()
    proposal_dir = os.path.join(store.reflections_dir, "task")
    os.makedirs(proposal_dir, exist_ok=True)
    path = os.path.join(proposal_dir, f"task_{task_id}.md")

    lines = [
        f"# MEMORY_UPDATE_PROPOSAL — task `{task_id}`",
        "",
        f"generated: {now_iso()}",
        f"task summary: {task_summary}",
        "",
        "## Reflection",
        "",
    ]
    for q in REFLECTION_QUESTIONS:
        lines.append(f"- **{q}** {answers.get(q, '')}".rstrip())

    for section, items in zip(PROPOSAL_SECTIONS,
                              (new_facts, new_decisions, new_lessons,
                               potential_skills, superseded_items,
                               open_questions)):
        lines.append("")
        lines.append(f"## {section}")
        if not items:
            lines.append("(none)")
        else:
            for item in items:
                if isinstance(item, dict):
                    lines.append("- " + " | ".join(f"{k}={v}" for k, v in item.items()))
                else:
                    lines.append(f"- {item}")

    lines.append("")
    lines.append("## Auto-commit")
    committed = []
    reviewed = []

    for fact in new_facts:
        decision = _commit_fact(store, fact, canonical_source, confidence,
                                auto_commit)
        (committed if decision.get("committed") else reviewed).append(
            fact.get("topic") or fact.get("id") or "?")

    for lesson in new_lessons:
        if "lesson_id" in lesson:
            entry = lesson
        else:
            entry = store.add_lesson(
                trigger=lesson.get("trigger", task_summary),
                failure=lesson.get("failure", ""),
                root_cause=lesson.get("root_cause", ""),
                fix=lesson.get("fix", ""),
                generalizable_rule=lesson.get("generalizable_rule", ""),
                scope=lesson.get("scope", "project"),
                source=lesson.get("source", task_summary),
                confidence=lesson.get("confidence", "MEDIUM"))
        committed.append(entry["lesson_id"])

    for decision in new_decisions:
        entry = _commit_decision(store, decision, canonical_source, confidence,
                                 auto_commit)
        (committed if entry.get("committed") else reviewed).append(
            entry.get("decision_id") or decision.get("topic") or "?")

    for q in open_questions:
        existing = store.open_questions()
        existing.setdefault("questions", [])
        if q not in existing["questions"]:
            existing["questions"].append(q)
        store.set_open_questions(existing)

    lines.append(f"- committed: {', '.join(committed) if committed else '(none)'}")
    lines.append(f"- requires_review: {', '.join(reviewed) if reviewed else '(none)'}")
    lines.append("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return path


def _commit_fact(store: MemoryStore, fact: dict, canonical_source: str | None,
                 confidence: str, auto_commit: bool) -> dict:
    """Auto-commit an accepted conclusion only when the unified transition
    policy allows it (registry canonical + HIGH + no conflict). Else the claim
    is recorded as a CANDIDATE pending change requiring review."""
    topic = fact.get("topic", "?")
    value = fact.get("value", "")
    source = fact.get("source") or canonical_source or ""
    outcomes = store.update_scientific_state(
        {topic: value}, source=source, auto_commit=auto_commit,
        confidence=fact.get("confidence", confidence))
    outcome = outcomes.get(topic, {})
    outcome["committed"] = (outcome.get("status") == "ACCEPTED")
    return outcome


def _commit_decision(store: MemoryStore, decision: dict,
                     canonical_source: str | None, confidence: str,
                     auto_commit: bool) -> dict:
    """Record one reflection decision under the v0.1.2 safety policy.

    `store.add_decision` itself enforces the policy (default CANDIDATE,
    ACCEPTED only when canonical+HIGH+no-conflict), so reflection never
    re-derives the rule and never reaches into private API.
    """
    source = decision.get("source") or canonical_source or ""
    conf = decision.get("confidence", confidence)
    entry = store.add_decision(
        topic=decision.get("topic", "?"),
        decision=decision.get("decision", ""),
        reason=decision.get("reason", ""),
        source=source,
        alternatives=decision.get("alternatives"),
        evidence=decision.get("evidence"),
        confidence=conf,
        status="ACCEPTED" if auto_commit else "CANDIDATE",
        detect_contradictions=True)
    entry["committed"] = (entry.get("status") == "ACCEPTED"
                          and not entry.get("requires_review", False))
    return entry
