#!/usr/bin/env python3
"""materials-memory — unified CLI for the DSH materials research memory system.

Every DSH-side wrapper (Cordis bridge, DSH skill, or the agent directly)
consumes this same interface:

  materials-memory init | brief | retrieve | reflect | accept-decision |
                     accept-change | propose-skills | promote-skill |
                     snapshot | rollback | status | metrics | test-retrieval

(ingest is planned for a future release and is not part of the CLI yet.)

Run `materials-memory.py --help` for details.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import (MemoryStore, Retriever, reflect_task, LessonManager,
                  SkillPromoter, SnapshotManager, ScientificClaimGate,
                  now_iso, now_date)  # noqa: E402

DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The single source of truth for the public CLI verb set. plugin.yaml's
# cli.verbs MUST match this (enforced by tests/test_cli_consistency.py).
CLI_VERBS = [
    "init", "brief", "retrieve", "reflect", "accept-decision", "accept-change",
    "propose-skills", "promote-skill", "snapshot", "rollback",
    "status", "metrics", "test-retrieval",
]

# session-start brief budget (spec §12: <= 8000 tokens)
BRIEF_BUDGET_TOKENS = 8000


def _reconfigure_stdio() -> None:
    """Emit UTF-8 on Windows GBK consoles instead of crashing on non-GBK
    characters (e.g. 'Å' in recalled text or CJK in briefs). errors='replace'
    keeps output lossy-but-alive even on a truly non-UTF-8 terminal."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):  # pragma: no cover - terminal quirks
                pass


_reconfigure_stdio()


def _estimate_tokens(text: str) -> int:
    # heuristic: CJK ~1 token per char, latin ~1 token per 4 chars
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    latin = max(0, len(text) - cjk)
    return cjk + latin // 4


def _open_store(root: str, active_profile: str | None = None) -> MemoryStore:
    store = MemoryStore(root, active_profile=active_profile)
    store.ensure_layout()
    return store


def _skill_files(store: MemoryStore) -> list[str]:
    """Indexed skill files: CORE skills plus the ACTIVE profile's skills
    (P0-9). Listed with their location prefix so core vs profile is visible."""
    out = []
    for fname in sorted(os.listdir(store.core_skills_dir)):
        if fname.endswith(".md"):
            out.append(f"core/{fname}")
    profile_dir = store.profile_skills_dir
    if profile_dir and os.path.isdir(profile_dir):
        for fname in sorted(os.listdir(profile_dir)):
            if fname.endswith(".md"):
                out.append(f"{store.active_profile}/{fname}")
    return out


# --------------------------------------------------------------------- verbs
def cmd_init(args) -> int:
    store = _open_store(args.root, args.profile)
    store.seed()
    print(f"initialized memory layout at {store.root}")
    return 0


def cmd_brief(args) -> int:
    """Generate PROJECT_BRIEF.md (session start) within the token budget."""
    store = _open_store(args.root, args.profile)
    state = store.scientific_state()
    pm = store.project_memory()
    lines = [
        "# PROJECT_BRIEF",
        "",
        f"generated: {now_iso()}",
        f"project memory: {os.path.relpath(store.project_memory_path, store.root)}",
        "",
        "## Current project",
        pm[:4000],
        "",
        "## Current stage",
        str(state.get("current_stage", "")),
        "",
        "## Canonical definitions (frozen)",
        json.dumps(state.get("frozen_definitions", {}), ensure_ascii=False, indent=2),
        "",
        "## Latest conclusions",
        json.dumps(state.get("current_conclusions", {}), ensure_ascii=False, indent=2),
        "",
        "## Blocking issues",
        json.dumps(state.get("blockers", []), ensure_ascii=False, indent=2),
        "",
        "## Active tasks / next steps",
        json.dumps(state.get("next_steps", []), ensure_ascii=False, indent=2),
        "",
    ]
    text = "\n".join(lines)
    # enforce budget
    while _estimate_tokens(text) > BRIEF_BUDGET_TOKENS and len(text) > 2000:
        text = text[: int(len(text) * 0.9)]
        text += "\n[... truncated to token budget]"
    out = os.path.join(store.outputs_dir, "PROJECT_BRIEF.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {out} (est. {_estimate_tokens(text)} tokens; "
          f"budget {BRIEF_BUDGET_TOKENS})")
    return 0


def cmd_retrieve(args) -> int:
    store = _open_store(args.root, args.profile)
    retriever = Retriever(store)
    hits = retriever.retrieve_text(args.query, k=args.k)
    print(json.dumps(hits, ensure_ascii=False, indent=2))
    return 0


def cmd_reflect(args) -> int:
    store = _open_store(args.root, args.profile)
    answers = dict(zip(
        ["What new fact was established?", "What assumption failed?",
         "What decision changed?", "What failure occurred?", "What fixed it?",
         "Is it reusable?", "Did canonical data change?",
         "Was anything superseded?", "What remains unresolved?"],
        args.answer if args.answer else [""] * 9))
    path = reflect_task(
        store, task_id=args.task_id, task_summary=args.summary,
        answers=answers,
        new_facts=_parse_json(args.facts),
        new_decisions=_parse_json(args.decisions),
        new_lessons=_parse_json(args.lessons),
        potential_skills=args.potential_skills or [],
        superseded_items=_parse_json(args.superseded),
        open_questions=args.open_questions or [],
        canonical_source=args.canonical_source, confidence=args.confidence,
        auto_commit=not args.no_auto_commit)
    print(f"wrote {path}")
    return 0


def cmd_accept_decision(args) -> int:
    """Explicit reviewer approval for one decision (P0-4 safety path).

    Only after this call may a conflicting decision supersede an ACCEPTED
    prior decision. Prior decisions are never auto-superseded.
    """
    store = _open_store(args.root, args.profile)
    entry = store.accept_decision(args.decision_id, reviewer=args.reviewer)
    print(json.dumps({
        "decision_id": entry["decision_id"],
        "status": entry["status"],
        "requires_review": entry.get("requires_review", False),
        "reviewed_by": entry.get("reviewed_by"),
        "contradictions": entry.get("contradictions", []),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_accept_change(args) -> int:
    """Explicit reviewer approval for one pending scientific-state change
    (P0-3). Only here may a conflicting new claim supersede an ACCEPTED one;
    change_id is a stable identity, never an array index."""
    store = _open_store(args.root, args.profile)
    claim = store.accept_change(args.change_id, reviewer=args.reviewer)
    print(json.dumps(claim, ensure_ascii=False, indent=2))
    return 0


def cmd_propose_skills(args) -> int:
    store = _open_store(args.root, args.profile)
    path = SkillPromoter(store).propose()
    print(f"wrote {path}")
    return 0


def cmd_promote_skill(args) -> int:
    store = _open_store(args.root, args.profile)
    path = SkillPromoter(store).promote(
        name=args.name, purpose=args.purpose, when_to_use=args.when_to_use,
        inputs=args.inputs, definitions=args.definitions,
        procedure=args.procedure, qa=args.qa,
        common_failures=args.common_failures,
        blocking_conditions=args.blocking_conditions, outputs=args.outputs,
        provenance_requirements=args.provenance_requirements,
        origin_lessons=args.origin_lessons, reviewer=args.reviewer)
    print(f"wrote {path}")
    return 0


def cmd_snapshot(args) -> int:
    store = _open_store(args.root, args.profile)
    path = SnapshotManager(store).create(args.milestone)
    print(f"snapshot: {path}")
    return 0


def cmd_rollback(args) -> int:
    store = _open_store(args.root, args.profile)
    SnapshotManager(store).rollback(args.dir)
    print(f"rolled back from {args.dir}")
    return 0


def cmd_status(args) -> int:
    store = _open_store(args.root, args.profile)
    print(f"root: {store.root}")
    print(f"project initialized: {'YES' if store.is_initialized() else 'NO'}")
    print(f"active profile: {store.active_profile or '(none)'}")
    print(f"project memory: {'YES' if os.path.exists(store.project_memory_path) and os.path.getsize(store.project_memory_path) else 'NO'}")
    print(f"scientific state: {'YES' if store.scientific_state() else 'NO'}")
    print(f"decisions: {len(store.decisions())}")
    print(f"lessons: {len(store.lessons())}")
    print(f"data registry datasets: {len(store.data_registry().get('datasets', []))}")
    print(f"methods: {len(store.method_registry().get('methods', []))}")
    print(f"open questions: {len(store.open_questions().get('questions', []))}")
    skills = _skill_files(store)
    print(f"skills: {len(skills)} -> {', '.join(skills) or '(none)'}")
    return 0


def cmd_metrics(args) -> int:
    """Compute the evolution metrics (spec §28)."""
    store = _open_store(args.root, args.profile)
    decisions = store.decisions()
    lessons = store.lessons()
    datasets = store.data_registry().get("datasets", [])
    skills = _skill_files(store)
    total_lessons = len(lessons) or 1
    metrics = {
        # share of lessons reused (times_verified >= 1)
        "LESSON_REUSE_RATE": round(
            sum(1 for l in lessons if l.get("times_verified", 0) >= 1) / total_lessons, 3),
        # share of lessons that recurred (times_verified >= 2) — higher = repeated
        "REPEATED_FAILURE_RATE": round(
            sum(1 for l in lessons if l.get("times_verified", 0) >= 2) / total_lessons, 3),
        "SKILL_REUSE_RATE": round(min(1.0, len(skills) / 5), 3),
        "PROVENANCE_COMPLETENESS": round(
            sum(1 for d in decisions
                if all(k in d for k in ("source", "status", "confidence"))
                and ("date" in d or "timestamp" in d))
            / max(1, len(decisions)), 3),
        "CONTRADICTION_DETECTION_RATE": round(
            sum(1 for d in decisions if d.get("status") == "SUPERSEDED"
                or d.get("contradictions")) / max(1, len(decisions)), 3),
        "CANONICAL_SOURCE_ACCURACY": round(
            sum(1 for d in decisions if "canonical" in str(d.get("source", "")).lower()
                or "frozen" in str(d.get("source", "")).lower())
            / max(1, len(decisions)), 3),
        # retrieved-at-least-once is approximated by lesson reuse
        "MEMORY_RECALL_RATE": round(
            sum(1 for l in lessons if l.get("status") in ("VERIFIED", "PROMOTED"))
            / total_lessons, 3),
    }
    print(json.dumps(metrics, indent=2))
    return 0


def cmd_test_retrieval(args) -> int:
    """Run three generic session-question retrieval checks (spec §32)."""
    store = _open_store(args.root, args.profile)
    retriever = Retriever(store)
    questions = [
        "现在三物种分类的最终结论是什么？",
        "Vcav 是不是 intrinsic radius？",
        "机制现在可以直接做吗？",
    ]
    for q in questions:
        hits = retriever.retrieve_text(q, k=3)
        print(f"Q: {q}")
        for hit in hits:
            print(f"  [{hit['score']}] {hit['kind']}:{hit['id']} -> "
                  f"{hit['text'][:120]!r}")
        print()
    return 0


# ------------------------------------------------------------------- parsing
def _parse_json(raw: list[str] | None) -> list[dict]:
    if not raw:
        return []
    if len(raw) == 1:
        try:
            value = json.loads(raw[0])
            if isinstance(value, list):
                return value
        except json.JSONDecodeError:
            pass
    out = []
    for item in raw:
        try:
            out.append(json.loads(item))
        except json.JSONDecodeError:
            out.append({"raw": item})
    return out


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser. Exposed for the verb-consistency test."""
    parser = argparse.ArgumentParser(
        prog="materials-memory",
        description="DSH materials research memory & self-evolution service")
    parser.add_argument("--root", default=DEFAULT_ROOT,
                        help="plugin/memory root (default: plugin dir)")
    parser.add_argument("--profile", default=None,
                        help="active project profile id (decides which project "
                             "skills are indexed; default: .active_profile marker)")
    sub = parser.add_subparsers(dest="verb", required=True)

    p = sub.add_parser("init", help="create memory layout and empty files (idempotent)")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("brief", help="generate PROJECT_BRIEF.md (session start)")
    p.set_defaults(func=cmd_brief)

    p = sub.add_parser("retrieve", help="retrieve top-k memories for a query")
    p.add_argument("query")
    p.add_argument("-k", type=int, default=5)
    p.set_defaults(func=cmd_retrieve)

    p = sub.add_parser("reflect", help="task-end reflection -> proposal")
    p.add_argument("--task-id", required=True)
    p.add_argument("--summary", default="")
    p.add_argument("--answer", action="append", default=[])
    p.add_argument("--facts", action="append", default=[])
    p.add_argument("--decisions", action="append", default=[])
    p.add_argument("--lessons", action="append", default=[])
    p.add_argument("--potential-skills", action="append", default=[])
    p.add_argument("--superseded", action="append", default=[])
    p.add_argument("--open-questions", action="append", default=[])
    p.add_argument("--canonical-source", default=None)
    p.add_argument("--confidence", default="HIGH")
    p.add_argument("--no-auto-commit", action="store_true")
    p.set_defaults(func=cmd_reflect)

    p = sub.add_parser(
        "accept-decision",
        help="reviewer-approve one decision (explicit supersede path)")
    p.add_argument("decision_id")
    p.add_argument("--reviewer", default="human")
    p.set_defaults(func=cmd_accept_decision)

    p = sub.add_parser(
        "accept-change",
        help="reviewer-approve one pending scientific-state change by stable "
             "change_id (explicit supersede path)")
    p.add_argument("change_id")
    p.add_argument("--reviewer", default="human")
    p.set_defaults(func=cmd_accept_change)

    p = sub.add_parser("propose-skills", help="write SKILL_PROMOTION_PROPOSAL.md")
    p.set_defaults(func=cmd_propose_skills)

    p = sub.add_parser("promote-skill", help="write a real skill file (approval path)")
    for name in ("name", "purpose", "when_to_use", "inputs", "definitions",
                 "procedure", "qa", "common_failures", "blocking_conditions",
                 "outputs", "provenance_requirements"):
        p.add_argument(f"--{name}", required=True)
    p.add_argument("--origin-lessons", action="append", required=True)
    p.add_argument("--reviewer", default="human")
    p.set_defaults(func=cmd_promote_skill)

    p = sub.add_parser("snapshot", help="snapshot memory at a milestone")
    p.add_argument("--milestone", required=True)
    p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("rollback", help="rollback memory from a snapshot dir")
    p.add_argument("dir")
    p.set_defaults(func=cmd_rollback)

    sub.add_parser("status", help="memory status").set_defaults(func=cmd_status)
    sub.add_parser("metrics", help="evolution metrics").set_defaults(func=cmd_metrics)
    sub.add_parser("test-retrieval", help="run §32 retrieval checks").set_defaults(
        func=cmd_test_retrieval)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
