from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Any

from pipeline.content_pipeline import (
    JsonModel,
    ResearchBackend,
    clean_documents,
    deduplicate_facts,
    extract_facts,
    plan_queries,
    plan_script,
    validate_final_script,
    write_script,
)


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _rank_candidates(
    topic: str,
    candidates: list[dict[str, Any]],
    model: JsonModel,
    *,
    include_text: bool,
) -> dict[str, dict[str, Any]]:
    score_schema = _schema(
        {
            "candidate_id": {"type": "string"},
            "score": {"type": "integer", "minimum": 0, "maximum": 100},
            "reason": {"type": "string"},
        },
        ["candidate_id", "score", "reason"],
    )
    schema = _schema(
        {"rankings": {"type": "array", "minItems": 1, "items": score_schema}},
        ["rankings"],
    )
    instruction = (
        "Score each Wikipedia candidate for whether it directly answers its assigned query. "
        "Penalize tangential, fictional, ambiguous, generic, and wrong-domain pages. "
        "A score of 65 or more means the page contains usable evidence for the query."
    )
    if include_text:
        instruction += " Base the score primarily on the supplied article excerpt, not the title."
    result = model.complete_json(
        instruction,
        json.dumps({"topic": topic, "candidates": candidates}),
        schema,
    )
    return {item["candidate_id"]: item for item in result["rankings"]}


def retrieve_sources(
    queries: dict[str, Any],
    backend: ResearchBackend,
    model: JsonModel,
    per_query: int = 3,
    threshold: int = 65,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    candidate_number = 1

    for query_index, query in enumerate(queries["queries"], start=1):
        seen_urls: set[str] = set()
        variants = [query, f"{queries['topic']} {query}"]
        for search_query in variants:
            for result in backend.search(search_query, limit=per_query):
                if result["url"] in seen_urls:
                    continue
                seen_urls.add(result["url"])
                candidates.append(
                    {
                        "candidate_id": f"C{candidate_number}",
                        "query_id": f"Q{query_index}",
                        "query": query,
                        "search_query": search_query,
                        **result,
                    }
                )
                candidate_number += 1

    if not candidates:
        raise ValueError("research returned no source candidates")

    scores = _rank_candidates(queries["topic"], candidates, model, include_text=False)
    selected: list[dict[str, Any]] = []

    for query_index, query in enumerate(queries["queries"], start=1):
        group = [
            candidate
            for candidate in candidates
            if candidate["query_id"] == f"Q{query_index}"
            and candidate["candidate_id"] in scores
        ]
        group.sort(
            key=lambda candidate: scores[candidate["candidate_id"]]["score"],
            reverse=True,
        )

        best_score = scores[group[0]["candidate_id"]]["score"] if group else -1
        if group and best_score < threshold:
            expanded: list[dict[str, Any]] = []
            for candidate in group[:4]:
                text = html.unescape(backend.fetch(candidate["url"]))
                text = re.sub(r"\s+", " ", text).strip()[:1400]
                expanded.append({**candidate, "article_excerpt": text})
            reranked = _rank_candidates(
                queries["topic"], expanded, model, include_text=True
            )
            scores.update(reranked)
            group.sort(
                key=lambda candidate: scores[candidate["candidate_id"]]["score"],
                reverse=True,
            )
            best_score = scores[group[0]["candidate_id"]]["score"] if group else -1

        if not group or best_score < threshold:
            raise ValueError(
                f"no sufficiently relevant source for query: {query}; "
                f"best score={best_score}"
            )

        best = group[0]
        selected.append(
            {
                "query_id": best["query_id"],
                "query": query,
                "title": best["title"],
                "url": best["url"],
                "relevance_score": scores[best["candidate_id"]]["score"],
                "relevance_reason": scores[best["candidate_id"]]["reason"],
            }
        )

    return {
        "topic": queries["topic"],
        "required_concepts": queries["required_concepts"],
        "sources": selected,
        "candidates_considered": len(candidates),
    }


@dataclass
class ContentPipeline:
    model: JsonModel
    research: ResearchBackend

    def run(self, topic: str) -> dict[str, dict[str, Any]]:
        artifacts: dict[str, dict[str, Any]] = {}
        artifacts["01_queries"] = plan_queries(topic, self.model)
        artifacts["02_sources"] = retrieve_sources(
            artifacts["01_queries"], self.research, self.model
        )
        artifacts["03_documents"] = clean_documents(
            artifacts["02_sources"], self.research
        )
        artifacts["04_facts"] = extract_facts(
            artifacts["03_documents"], self.model
        )
        artifacts["05_knowledge"] = deduplicate_facts(
            artifacts["04_facts"], self.model
        )
        artifacts["06_plan"] = plan_script(
            artifacts["05_knowledge"], self.model
        )
        artifacts["07_script"] = write_script(
            artifacts["05_knowledge"], artifacts["06_plan"], self.model
        )
        artifacts["08_validation"] = validate_final_script(
            artifacts["07_script"], artifacts["05_knowledge"]
        )
        if not artifacts["08_validation"]["valid"]:
            raise ValueError(
                "script validation failed: "
                + "; ".join(artifacts["08_validation"]["errors"])
            )
        return artifacts
