from __future__ import annotations

import html
import json
import math
import re
from collections import Counter
from typing import Any

from pipeline.content_pipeline import JsonModel, ResearchBackend


_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "in", "is", "it", "of", "on", "or", "that", "the", "their", "this", "to",
    "what", "when", "where", "which", "why", "with", "across", "different",
}


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", text.casefold())
        if len(token) > 2 and token not in _STOP_WORDS
    ]


def _canonical_url(url: str) -> str:
    # The research adapters already return canonical URLs. This deliberately
    # removes only fragments so it remains safe for arbitrary backends.
    return url.strip().split("#", 1)[0].rstrip("/")


def _query_variants(query: str, topic: str) -> list[str]:
    """Create generic search variants without topic-specific rules."""
    query_terms = _tokens(query)
    topic_terms = _tokens(topic)
    compact = " ".join(dict.fromkeys(query_terms))
    combined = " ".join(dict.fromkeys([*topic_terms, *query_terms]))
    variants = [query, compact, combined]

    result: list[str] = []
    seen: set[str] = set()
    for variant in variants:
        cleaned = " ".join(variant.split())
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def _lexical_score(query: str, topic: str, candidate: dict[str, Any]) -> float:
    """BM25-like deterministic pre-ranking over title, snippet and excerpt."""
    query_tokens = list(dict.fromkeys([*_tokens(query), *_tokens(topic)]))
    if not query_tokens:
        return 0.0

    title = candidate.get("title", "")
    snippet = candidate.get("snippet", "")
    excerpt = candidate.get("excerpt", "")
    title_counts = Counter(_tokens(title))
    body_counts = Counter(_tokens(f"{snippet} {excerpt}"))

    score = 0.0
    for token in query_tokens:
        if title_counts[token]:
            score += 4.0
        frequency = body_counts[token]
        if frequency:
            score += 1.0 + math.log1p(frequency)

    phrase = " ".join(_tokens(query))
    searchable = f"{title} {snippet} {excerpt}".casefold()
    if phrase and phrase in searchable:
        score += 6.0
    return round(score, 3)


def _select_with_model(
    topic: str,
    query: str,
    candidates: list[dict[str, Any]],
    model: JsonModel,
) -> tuple[str | None, str]:
    schema = {
        "type": "object",
        "properties": {
            "selected_candidate_id": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["selected_candidate_id", "reason"],
        "additionalProperties": False,
    }
    compact = [
        {
            "candidate_id": candidate["candidate_id"],
            "title": candidate.get("title", ""),
            "url": candidate.get("url", ""),
            "excerpt": candidate.get("excerpt", "")[:1600],
        }
        for candidate in candidates
    ]
    result = model.complete_json(
        "Select the single passage that best contains evidence answering the exact research question. "
        "Compare the passages relative to one another. Select an ID only from the supplied candidates. "
        "Do not assign an absolute relevance score and do not reject a useful passage merely because it "
        "does not answer every aspect of the broader topic.",
        json.dumps({"topic": topic, "research_question": query, "candidates": compact}),
        schema,
    )
    selected_id = result.get("selected_candidate_id", "")
    valid_ids = {candidate["candidate_id"] for candidate in candidates}
    return (selected_id if selected_id in valid_ids else None), result.get("reason", "")


def retrieve_sources_evidence_first(
    queries: dict[str, Any],
    backend: ResearchBackend,
    model: JsonModel,
    per_query: int = 3,
    shortlist_size: int = 5,
    min_excerpt_chars: int = 200,
) -> dict[str, Any]:
    """Retrieve sources using fetched evidence before model selection.

    Search, fetching, deterministic pre-ranking and model comparison are kept
    separate. A query fails only when no usable document can be fetched after
    generic query expansion, not because a model emitted a low arbitrary score.
    """
    selected: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    total_candidates = 0
    next_candidate = 1

    for query_index, query in enumerate(queries["queries"], start=1):
        query_id = f"Q{query_index}"
        candidates: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        search_variants = _query_variants(query, queries["topic"])

        for search_query in search_variants:
            for result in backend.search(search_query, limit=per_query):
                url = _canonical_url(result.get("url", ""))
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                excerpt = ""
                fetch_error = ""
                try:
                    excerpt = _normalise(backend.fetch(url))[:2400]
                except Exception as exc:  # One inaccessible result must not abort retrieval.
                    fetch_error = f"{type(exc).__name__}: {exc}"

                candidate = {
                    "candidate_id": f"C{next_candidate}",
                    "query_id": query_id,
                    "query": query,
                    "search_query": search_query,
                    **result,
                    "url": url,
                    "excerpt": excerpt,
                    "fetch_error": fetch_error,
                }
                candidate["lexical_score"] = _lexical_score(
                    query, queries["topic"], candidate
                )
                candidates.append(candidate)
                next_candidate += 1

        total_candidates += len(candidates)
        usable = [
            candidate
            for candidate in candidates
            if len(candidate["excerpt"]) >= min_excerpt_chars
        ]
        usable.sort(
            key=lambda candidate: (
                candidate["lexical_score"],
                len(candidate["excerpt"]),
            ),
            reverse=True,
        )

        if not usable:
            errors = [
                candidate["fetch_error"]
                for candidate in candidates
                if candidate["fetch_error"]
            ]
            raise ValueError(
                f"no usable source document for query: {query}; "
                f"searched={search_variants}; fetch_errors={errors[:3]}"
            )

        shortlist = usable[:shortlist_size]
        selected_id, reason = _select_with_model(
            queries["topic"], query, shortlist, model
        )

        # Invalid model output falls back to the deterministic best passage.
        # This is deliberately not a score threshold: the document has already
        # passed the usable-evidence gate and remains available to fact validation.
        best = next(
            (candidate for candidate in shortlist if candidate["candidate_id"] == selected_id),
            shortlist[0],
        )
        selection_method = "model-comparison" if selected_id else "deterministic-fallback"

        selected.append(
            {
                "query_id": query_id,
                "query": query,
                "title": best.get("title", ""),
                "url": best["url"],
                "relevance_score": best["lexical_score"],
                "relevance_reason": reason or "highest deterministic evidence score",
                "retrieval_fallback_used": len(search_variants) > 1,
                "selection_method": selection_method,
            }
        )
        diagnostics.append(
            {
                "query_id": query_id,
                "query": query,
                "search_variants": search_variants,
                "usable_candidates": len(usable),
                "selection_method": selection_method,
                "selected_candidate_id": best["candidate_id"],
                "candidate_scores": [
                    {
                        "candidate_id": candidate["candidate_id"],
                        "title": candidate.get("title", ""),
                        "url": candidate["url"],
                        "lexical_score": candidate["lexical_score"],
                        "excerpt_chars": len(candidate["excerpt"]),
                    }
                    for candidate in shortlist
                ],
            }
        )

    return {
        "topic": queries["topic"],
        "required_concepts": queries["required_concepts"],
        "sources": selected,
        "candidates_considered": total_candidates,
        "retrieval_strategy": "evidence-first-comparative-selection",
        "diagnostics": diagnostics,
    }
