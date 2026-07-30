from __future__ import annotations

import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


class JsonModel(Protocol):
    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]: ...


class ResearchBackend(Protocol):
    def search(self, query: str, limit: int = 3) -> list[dict[str, str]]: ...
    def fetch(self, url: str) -> str: ...


class GitHubModelsClient:
    endpoint = "https://models.github.ai/inference/chat/completions"

    def __init__(self, token: str | None = None, model: str | None = None):
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.model = model or os.environ.get("GITHUB_MODELS_MODEL", "openai/gpt-4.1")
        if not self.token:
            raise RuntimeError("GITHUB_TOKEN is required for GitHub Models")

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        body = {
            "model": self.model,
            "temperature": 0.1,
            "seed": 17,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "pipeline_result", "strict": True, "schema": schema}},
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2026-03-10",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub Models request failed: HTTP {exc.code}: {detail}") from exc
        return json.loads(payload["choices"][0]["message"]["content"])


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def validate_non_empty_list(payload: dict[str, Any], field: str) -> list[Any]:
    value = payload.get(field)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty list")
    return value


def plan_queries(topic: str, model: JsonModel) -> dict[str, Any]:
    schema = _schema(
        {
            "topic": {"type": "string"},
            "queries": {"type": "array", "minItems": 4, "maxItems": 8, "items": {"type": "string"}},
            "required_concepts": {"type": "array", "minItems": 3, "maxItems": 10, "items": {"type": "string"}},
        },
        ["topic", "queries", "required_concepts"],
    )
    result = model.complete_json(
        "Generate precise, non-overlapping research queries and a compact list of concepts a correct explainer must cover. Include causes, mechanisms, measurement, concrete examples, scale, and misconceptions where relevant.",
        f"Topic: {topic}",
        schema,
    )
    validate_non_empty_list(result, "queries")
    validate_non_empty_list(result, "required_concepts")
    return result


def _canonical_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, value) for key, value in query if not key.lower().startswith("utm_") and key.lower() not in {"gclid", "fbclid"}]
    path = parsed.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, urllib.parse.urlencode(query), ""))


def _query_variants(query: str, topic: str) -> list[str]:
    variants = [query, f"{query} explanation", f"{query} {topic}"]
    seen: set[str] = set()
    result: list[str] = []
    for variant in variants:
        normalised = _normalise(variant)
        if normalised and normalised not in seen:
            seen.add(normalised)
            result.append(variant)
    return result


def _score_candidates(topic: str, candidates: list[dict[str, Any]], model: JsonModel, *, using_excerpts: bool = False) -> dict[str, dict[str, Any]]:
    score_schema = _schema(
        {
            "candidate_id": {"type": "string"},
            "score": {"type": "integer", "minimum": 0, "maximum": 100},
            "reason": {"type": "string"},
        },
        ["candidate_id", "score", "reason"],
    )
    schema = _schema({"rankings": {"type": "array", "minItems": 1, "items": score_schema}}, ["rankings"])
    evidence = "title, snippet, and fetched excerpt" if using_excerpts else "title and snippet"
    ranking = model.complete_json(
        f"Score each candidate for direct semantic relevance to its assigned query using its {evidence}. Penalize tangential, fictional, ambiguous, or wrong-domain pages. Do not reward a page merely because it shares a keyword.",
        json.dumps({"topic": topic, "candidates": candidates}),
        schema,
    )
    return {item["candidate_id"]: item for item in ranking["rankings"]}


def retrieve_sources(queries: dict[str, Any], backend: ResearchBackend, model: JsonModel, per_query: int = 3, threshold: int = 65) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    seen_urls: set[tuple[str, str]] = set()
    candidate_id = 1

    def add_results(query_id: str, query: str, search_query: str) -> None:
        nonlocal candidate_id
        for result in backend.search(search_query, limit=per_query):
            url = result.get("url", "").strip()
            if not url:
                continue
            canonical = _canonical_url(url)
            dedupe_key = (query_id, canonical)
            if dedupe_key in seen_urls:
                continue
            seen_urls.add(dedupe_key)
            candidates.append({
                "candidate_id": f"C{candidate_id}",
                "query_id": query_id,
                "query": query,
                "search_query": search_query,
                **result,
                "url": canonical,
            })
            candidate_id += 1

    for query_index, query in enumerate(queries["queries"], start=1):
        add_results(f"Q{query_index}", query, query)
    if not candidates:
        raise ValueError("research returned no source candidates")

    scores = _score_candidates(queries["topic"], candidates, model)
    selected: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []

    for query_index, query in enumerate(queries["queries"], start=1):
        query_id = f"Q{query_index}"
        group = [c for c in candidates if c["query_id"] == query_id and c["candidate_id"] in scores]
        group.sort(key=lambda c: scores[c["candidate_id"]]["score"], reverse=True)
        initial_top_score = scores[group[0]["candidate_id"]]["score"] if group else None
        fallback_used = not group or initial_top_score < threshold

        if fallback_used:
            for variant in _query_variants(query, queries["topic"])[1:]:
                add_results(query_id, query, variant)
            group = [c for c in candidates if c["query_id"] == query_id]
            rerank_candidates: list[dict[str, Any]] = []
            for candidate in group:
                excerpt = ""
                fetch_error = ""
                try:
                    excerpt = re.sub(r"\s+", " ", html.unescape(backend.fetch(candidate["url"]))).strip()[:1200]
                except Exception as exc:  # A single inaccessible page must not abort candidate evaluation.
                    fetch_error = f"{type(exc).__name__}: {exc}"
                rerank_candidates.append({**candidate, "excerpt": excerpt, "fetch_error": fetch_error})
            scores.update(_score_candidates(queries["topic"], rerank_candidates, model, using_excerpts=True))
            group = [c for c in group if c["candidate_id"] in scores]
            group.sort(key=lambda c: scores[c["candidate_id"]]["score"], reverse=True)

        top_score = scores[group[0]["candidate_id"]]["score"] if group else None
        diagnostics.append({
            "query_id": query_id,
            "query": query,
            "fallback_used": fallback_used,
            "initial_top_score": initial_top_score,
            "final_top_score": top_score,
            "candidate_scores": [
                {
                    "candidate_id": candidate["candidate_id"],
                    "title": candidate.get("title", ""),
                    "url": candidate.get("url", ""),
                    "score": scores[candidate["candidate_id"]]["score"],
                    "reason": scores[candidate["candidate_id"]]["reason"],
                }
                for candidate in group
            ],
        })
        if not group or top_score is None or top_score < threshold:
            details = ", ".join(f"{item['score']}:{item['title']}" for item in diagnostics[-1]["candidate_scores"][:5]) or "no scored candidates"
            raise ValueError(f"no sufficiently relevant source for query: {query}; threshold={threshold}; candidates={details}")

        best = group[0]
        selected.append({
            "query_id": best["query_id"],
            "query": query,
            "title": best["title"],
            "url": best["url"],
            "relevance_score": scores[best["candidate_id"]]["score"],
            "relevance_reason": scores[best["candidate_id"]]["reason"],
            "retrieval_fallback_used": fallback_used,
        })

    return {
        "topic": queries["topic"],
        "required_concepts": queries["required_concepts"],
        "sources": selected,
        "candidates_considered": len(candidates),
        "relevance_threshold": threshold,
        "diagnostics": diagnostics,
    }


def clean_documents(sources: dict[str, Any], backend: ResearchBackend, max_chars: int = 2400) -> dict[str, Any]:
    documents = []
    for source in sources["sources"]:
        text = html.unescape(backend.fetch(source["url"]))
        text = re.sub(r"\s+", " ", text).strip()[:max_chars]
        if len(text) >= 200:
            documents.append({**source, "text": text})
    covered = {d["query_id"] for d in documents}
    expected = {s["query_id"] for s in sources["sources"]}
    if covered != expected:
        raise ValueError(f"missing usable documents for queries: {sorted(expected - covered)}")
    return {"topic": sources["topic"], "required_concepts": sources["required_concepts"], "documents": documents}


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def extract_facts(documents: dict[str, Any], model: JsonModel) -> dict[str, Any]:
    fact_schema = _schema(
        {
            "query_id": {"type": "string"},
            "claim": {"type": "string"},
            "evidence_excerpt": {"type": "string"},
            "source_url": {"type": "string"},
            "source_title": {"type": "string"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
        ["query_id", "claim", "evidence_excerpt", "source_url", "source_title", "confidence"],
    )
    schema = _schema({"facts": {"type": "array", "minItems": 4, "maxItems": 24, "items": fact_schema}}, ["facts"])
    compact = [{"query_id": d["query_id"], "query": d["query"], "title": d["title"], "url": d["url"], "text": d["text"]} for d in documents["documents"]]
    result = model.complete_json(
        "Extract only atomic claims directly entailed by the supplied text. Copy a short exact evidence excerpt from the source text. Never combine multiple mechanisms unless the excerpt supports all of them. Produce at least one fact for every query_id.",
        json.dumps({"topic": documents["topic"], "required_concepts": documents["required_concepts"], "documents": compact}),
        schema,
    )
    validate_non_empty_list(result, "facts")
    docs_by_url = {d["url"]: d for d in documents["documents"]}
    expected_queries = {d["query_id"] for d in documents["documents"]}
    covered_queries: set[str] = set()
    for fact in result["facts"]:
        doc = docs_by_url.get(fact["source_url"])
        if not doc:
            raise ValueError("fact cites a source that was not retrieved")
        if fact["query_id"] != doc["query_id"]:
            raise ValueError("fact query_id does not match its source document")
        excerpt = _normalise(fact["evidence_excerpt"])
        if not excerpt or excerpt not in _normalise(doc["text"]):
            raise ValueError("fact evidence excerpt is not present in its source document")
        covered_queries.add(fact["query_id"])
    if covered_queries != expected_queries:
        raise ValueError(f"fact extraction missed queries: {sorted(expected_queries - covered_queries)}")
    return {"topic": documents["topic"], "required_concepts": documents["required_concepts"], **result}


def deduplicate_facts(facts: dict[str, Any], model: JsonModel) -> dict[str, Any]:
    item_schema = _schema(
        {
            "id": {"type": "string"},
            "claim": {"type": "string"},
            "query_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "source_urls": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "evidence_excerpts": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
        ["id", "claim", "query_ids", "source_urls", "evidence_excerpts", "confidence"],
    )
    schema = _schema(
        {"facts": {"type": "array", "minItems": 3, "maxItems": 16, "items": item_schema}, "conflicts": {"type": "array", "items": {"type": "string"}}},
        ["facts", "conflicts"],
    )
    result = model.complete_json(
        "Merge only genuinely equivalent claims. Preserve every query_id, source URL, and exact evidence excerpt. Do not broaden, infer, or add claims. Report genuine contradictions.",
        json.dumps(facts),
        schema,
    )
    validate_non_empty_list(result, "facts")
    source_urls = {f["source_url"] for f in facts["facts"]}
    query_ids = {f["query_id"] for f in facts["facts"]}
    for item in result["facts"]:
        if not set(item["source_urls"]).issubset(source_urls):
            raise ValueError("deduplication introduced an unknown source")
        if not set(item["query_ids"]).issubset(query_ids):
            raise ValueError("deduplication introduced an unknown query")
    return {"topic": facts["topic"], "required_concepts": facts["required_concepts"], **result}


def plan_script(knowledge: dict[str, Any], model: JsonModel) -> dict[str, Any]:
    beat_schema = _schema(
        {"purpose": {"type": "string"}, "fact_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}}, "visual_intent": {"type": "string"}},
        ["purpose", "fact_ids", "visual_intent"],
    )
    schema = _schema({"angle": {"type": "string"}, "beats": {"type": "array", "minItems": 4, "maxItems": 8, "items": beat_schema}}, ["angle", "beats"])
    result = model.complete_json(
        "Plan a clear 45-60 second explainer using only supplied facts. Cover at least 80 percent of represented query_ids and all required concepts that the evidence supports. Include one quantitative or concrete example only when explicitly supported.",
        json.dumps(knowledge),
        schema,
    )
    return {"topic": knowledge["topic"], **result}


def write_script(knowledge: dict[str, Any], plan: dict[str, Any], model: JsonModel) -> dict[str, Any]:
    segment_schema = _schema(
        {"narration": {"type": "string"}, "visual_query": {"type": "string"}, "fact_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}}},
        ["narration", "visual_query", "fact_ids"],
    )
    schema = _schema(
        {"topic": {"type": "string"}, "hook": {"type": "string"}, "segments": {"type": "array", "minItems": 4, "maxItems": 8, "items": segment_schema}, "cta": {"type": "string"}},
        ["topic", "hook", "segments", "cta"],
    )
    return model.complete_json(
        "Write natural spoken English for a curious adult in 110-150 words. Every factual clause must be no more specific than the cited fact claims. Never invent comparisons, locations, numbers, instruments, causes, or examples. Use short varied sentences and avoid generic hype. CTA may be empty.",
        json.dumps({"knowledge": knowledge, "plan": plan}),
        schema,
    )


def validate_final_script(script: dict[str, Any], knowledge: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    facts_by_id = {fact["id"]: fact for fact in knowledge["facts"]}
    used_ids: set[str] = set()
    if script.get("topic", "").strip() != knowledge["topic"].strip():
        errors.append("script topic does not match requested topic")
    segments = script.get("segments")
    if not isinstance(segments, list) or not segments:
        errors.append("segments must be non-empty")
        segments = []
    spoken = [script.get("hook", ""), script.get("cta", "")]
    for index, segment in enumerate(segments):
        narration = segment.get("narration", "")
        visual = segment.get("visual_query", "")
        ids = segment.get("fact_ids", [])
        spoken.append(narration)
        if not narration.strip() or not visual.strip():
            errors.append(f"segment {index} has empty narration or visual query")
        unknown = set(ids).difference(facts_by_id)
        if unknown:
            errors.append(f"segment {index} uses unknown fact IDs: {sorted(unknown)}")
        used_ids.update(ids)
    text = " ".join(spoken).strip()
    words = re.findall(r"\b[\w'-]+\b", text)
    if not 90 <= len(words) <= 170:
        errors.append(f"spoken word count {len(words)} is outside 90-170")
    for phrase in ("the surprising reason", "hidden secret", "hidden engineering problem"):
        if phrase in text.lower():
            errors.append(f"banned generic phrase: {phrase}")
    if not used_ids:
        errors.append("script uses no researched facts")

    all_query_ids = {qid for fact in facts_by_id.values() for qid in fact["query_ids"]}
    used_query_ids = {qid for fid in used_ids if fid in facts_by_id for qid in facts_by_id[fid]["query_ids"]}
    coverage = len(used_query_ids) / len(all_query_ids) if all_query_ids else 0.0
    if coverage < 0.8:
        errors.append(f"research-query coverage {coverage:.0%} is below 80%")

    source_urls = sorted({url for fid in used_ids if fid in facts_by_id for url in facts_by_id[fid]["source_urls"]})
    domains = sorted({urllib.parse.urlparse(url).netloc for url in source_urls})
    if len(domains) < 2:
        warnings.append("all cited evidence comes from one source domain; add an independent authoritative backend before production")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "word_count": len(words),
        "used_fact_ids": sorted(used_ids),
        "covered_query_ids": sorted(used_query_ids),
        "query_coverage": round(coverage, 3),
        "source_urls": source_urls,
        "source_domains": domains,
    }


@dataclass
class ContentPipeline:
    model: JsonModel
    research: ResearchBackend

    def run(self, topic: str) -> dict[str, dict[str, Any]]:
        artifacts: dict[str, dict[str, Any]] = {}
        artifacts["01_queries"] = plan_queries(topic, self.model)
        artifacts["02_sources"] = retrieve_sources(artifacts["01_queries"], self.research, self.model)
        artifacts["03_documents"] = clean_documents(artifacts["02_sources"], self.research)
        artifacts["04_facts"] = extract_facts(artifacts["03_documents"], self.model)
        artifacts["05_knowledge"] = deduplicate_facts(artifacts["04_facts"], self.model)
        artifacts["06_plan"] = plan_script(artifacts["05_knowledge"], self.model)
        artifacts["07_script"] = write_script(artifacts["05_knowledge"], artifacts["06_plan"], self.model)
        artifacts["08_validation"] = validate_final_script(artifacts["07_script"], artifacts["05_knowledge"])
        if not artifacts["08_validation"]["valid"]:
            raise ValueError("script validation failed: " + "; ".join(artifacts["08_validation"]["errors"]))
        return artifacts
