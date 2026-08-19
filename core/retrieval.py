"""Retrieval over the memory store.

Phase-1 strategy (no expensive embedding API required):
  * full-text token scoring (BM25-style) over every memory document,
    with field weights (scientific state / project memory rank higher);
  * optional SQLite FTS5 index when available (sqlite3 with FTS5);

Semantic retrieval may be layered on later, but the plugin never depends
on an embedding API to work.
"""

from __future__ import annotations

import math
import os
import re
import sqlite3
import unicodedata
from collections import Counter

from .memory_manager import MemoryStore

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "been", "it", "its", "this", "that",
    "as", "at", "by", "from", "not", "no", "do", "does", "did", "we", "you",
    "they", "he", "she", "i", "what", "which", "when", "where", "how", "why",
    "the", "of", "and", "in", "等", "与", "的",
}

# doc kinds -> search weight
_KIND_WEIGHT = {
    "project_memory": 3.0,
    "scientific_state": 3.0,
    "decision": 2.0,
    "lesson": 2.0,
    "skill": 2.0,
    "data_registry": 1.5,
    "method_registry": 1.5,
    "open_questions": 1.5,
    "case": 1.0,
}

# Kinds that carry the canonical long-term scientific state. When a query
# genuinely matches one of them (BM25 score > 0), at least one slot in the
# Top-K is reserved so skills/lessons can never drown out canonical memory.
CANONICAL_KINDS = ("project_memory", "scientific_state")

# Generic diversification cap: any single kind occupies at most this many
# positions in the Top-K (default 2), so no source type can monopolize the
# results regardless of how many documents of that kind exist.
DEFAULT_MAX_PER_KIND = 2


def tokenize(text: str) -> list[str]:
    """Case-fold, CJK-aware tokenization."""
    if not text:
        return []
    text = unicodedata.normalize("NFKC", text).lower()
    return [t for t in _TOKEN_RE.findall(text) if t not in _STOP]


def _corpus(store: MemoryStore, include_skills: bool = True) -> list[dict]:
    """{id, kind, text} rows over the ACTIVE project's memory plus the
    indexed skills.

    P0-9 isolation: only CORE skills (skills/core) plus the ACTIVE project
    profile's skills (profiles/<active_profile>/skills) are indexed. An
    inactive project profile is never read here, so a fresh generic project
    cannot retrieve another project's conclusions."""
    def doc(doc_id, kind, text):
        return {"id": doc_id, "kind": kind, "text": text}

    docs = []
    docs.append(doc("project_memory", "project_memory", store.project_memory()))
    state = store.scientific_state()
    docs.append(doc("scientific_state", "scientific_state", _flatten(state)))
    for d in store.decisions():
        docs.append(doc(f"decision:{d.get('decision_id')}", "decision",
                        " ".join(str(d.get(k, "")) for k in
                                 ("topic", "decision", "reason", "evidence"))))
    for l in store.lessons():
        docs.append(doc(f"lesson:{l.get('lesson_id')}", "lesson",
                        " ".join(str(l.get(k, "")) for k in
                                 ("trigger", "failure", "root_cause", "fix",
                                  "generalizable_rule", "scope"))))
    docs.append(doc("open_questions", "open_questions",
                    _flatten(store.open_questions())))
    reg = store.data_registry()
    docs.append(doc("data_registry", "data_registry", _flatten(reg)))
    docs.append(doc("method_registry", "method_registry",
                    _flatten(store.method_registry())))
    if include_skills:
        for root in (store.core_skills_dir, store.profile_skills_dir):
            if not root or not os.path.isdir(root):
                continue
            for fname in sorted(os.listdir(root)):
                if fname.endswith(".md"):
                    path = os.path.join(root, fname)
                    with open(path, "r", encoding="utf-8") as fh:
                        docs.append(doc(f"skill:{fname}", "skill", fh.read()))
    return docs


def _flatten(value, depth: int = 0) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten(v, depth + 1) for v in value.values())
    if isinstance(value, list):
        return " ".join(_flatten(v, depth + 1) for v in value)
    return str(value)


def _bm25(docs: list[dict], query_tokens: list[str], k1: float = 1.5,
          b: float = 0.75) -> list[tuple[str, str, float]]:
    if not query_tokens:
        return []
    q_tokens = set(query_tokens)
    doc_tokens = [tokenize(d["text"]) for d in docs]
    lengths = [len(t) for t in doc_tokens]
    avg_len = sum(lengths) / max(1, len(lengths))
    n_docs = len(docs)
    df = Counter()
    for toks in doc_tokens:
        for tok in set(toks):
            df[tok] += 1
    idf = {tok: math.log(1 + (n_docs - df[tok] + 0.5) / (df[tok] + 0.5))
           for tok in q_tokens}
    scored = []
    for idx, doc in enumerate(docs):
        freq = Counter(doc_tokens[idx])
        denom = lengths[idx] + k1 * (1 - b + b * lengths[idx] / avg_len) if avg_len else 1
        score = 0.0
        for tok in q_tokens:
            if freq[tok]:
                score += idf[tok] * (freq[tok] * (k1 + 1)) / (freq[tok] + denom)
        if score > 0:
            score *= _KIND_WEIGHT.get(doc["kind"], 1.0)
            scored.append((doc["id"], doc["kind"], score))
    scored.sort(key=lambda item: item[2], reverse=True)
    return scored


def _diversify(scored: list[tuple[str, str, float]], k: int,
               max_per_kind: int = DEFAULT_MAX_PER_KIND) -> list[tuple[str, str, float]]:
    """Generic kind diversification over BM25 results.

    Rules (v0.1.1, P0-3):
      1. Keep the BM25 ranking; only re-order selection, never re-score.
      2. Reserve ONE slot for the highest-scoring canonical-memory document
         (project_memory / scientific_state) when it genuinely matched the
         query (score > 0). A canonical doc with NO query-token overlap is
         never forced in.
      3. Cap any single kind at `max_per_kind` positions, so a corpus with
         many skills (or many decisions/lessons) cannot monopolize Top-K.
      4. Remaining positions fill by BM25 score subject to the caps.
    """
    if k <= 0 or not scored:
        return []
    canonical = [h for h in scored if h[1] in CANONICAL_KINDS and h[2] > 0]
    result: list[tuple[str, str, float]] = []
    counts: dict[str, int] = {}
    if canonical:
        best = canonical[0]  # scored is sorted desc, so this is the top canonical
        result.append(best)
        counts[best[1]] = 1
    for hit in scored:
        if len(result) >= k:
            break
        if hit in result:
            continue
        if counts.get(hit[1], 0) >= max_per_kind:
            continue
        result.append(hit)
        counts[hit[1]] = counts.get(hit[1], 0) + 1
    return result


class Retriever:
    """BM25-style retriever over a MemoryStore. Optionally mirrors into an
    in-memory SQLite FTS5 table when the build supports FTS5."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def retrieve(self, query: str, k: int = 5, *, include_skills: bool = True,
                 sources: list[str] | None = None,
                 max_per_kind: int = DEFAULT_MAX_PER_KIND) -> list[dict]:
        docs = _corpus(self.store, include_skills=include_skills)
        if sources:
            allowed = set(sources)
            docs = [d for d in docs if d["kind"] in allowed]
        hits = _diversify(_bm25(docs, tokenize(query)), k,
                          max_per_kind=max_per_kind)
        return [{"id": doc_id, "kind": kind, "score": round(score, 4)}
                for doc_id, kind, score in hits]

    def retrieve_text(self, query: str, k: int = 5, *,
                      include_skills: bool = True) -> list[dict]:
        """Return retrieved rows with their display text attached."""
        docs = {d["id"]: d for d in _corpus(self.store, include_skills=include_skills)}
        hits = self.retrieve(query, k=k, include_skills=include_skills)
        for hit in hits:
            hit["text"] = docs.get(hit["id"], {}).get("text", "")[:1200]
        return hits

    def build_fts5_index(self) -> str | None:
        """Optional: mirror corpus into SQLite FTS5 for phrase queries.
        Returns the sqlite file path or None when FTS5 is unavailable."""
        try:
            conn = sqlite3.connect(":memory:")
            conn.execute("CREATE VIRTUAL TABLE mem USING fts5(id, kind, body)")
            for doc in _corpus(self.store):
                conn.execute("INSERT INTO mem(id, kind, body) VALUES (?,?,?)",
                             (doc["id"], doc["kind"], doc["text"]))
            return conn
        except sqlite3.OperationalError:
            return None


def retrieve_top_k(store: MemoryStore, query: str, k: int = 5,
                   include_skills: bool = True) -> list[dict]:
    return Retriever(store).retrieve(query, k=k, include_skills=include_skills)
