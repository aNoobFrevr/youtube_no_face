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
    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        ...


class ResearchBackend(Protocol):
    def search(self, query: str, limit: int = 3) -> list[dict[str, str]]:
        ...

    def fetch(self, url: str) -> str:
        ...


class GitHubModelsClient:
    """Small dependency-free client for GitHub Models structured output."""

    endpoint = "https://models.github.ai/inference/chat/completions"

    def __init__(self, token: str | None = None, model: str | None = None):
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.model = model or os.environ.get("GITHUB_MODELS_MODEL", "openai/gpt-4.1")
        if not self.token:
            raise RuntimeError("GITHUB_TOKEN is required for GitHub Models")

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        body = {
            "model": self.model,
            "temperature": 0.2,
            "seed": 17,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "pipeline_result",
                    "strict": True,
                    "schema": schema,
                },
            },
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
        content = payload["choices"][0]["message"]["content"]
        return json.loads(content)


class WikipediaResearchBackend:
    """Initial zero-key retrieval adapter. Replaceable without changing later stages."""

    api = "https://en.wikipedia.org/w/api.php"

    def search(self, query: str, limit: int = 3) -> list[dict[str, str]]:
        params = urllib.parse.urlencode(
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "format": "json",
                "utf8": 1,
            }
        )
        request = urllib.request.Request(
            f"{self.api}?{params}", headers={"User-Agent": "youtube-no-face/0.1"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            results = json.load(response)["query"]["search"]
        return [
            {
                "title": item["title"],
                "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(item["title"].replace(" ", "_")),
            }
            for item in results
        ]

    def fetch(self, url: str) -> str:
        title = urllib.parse.unquote(url.rsplit("/", 1)[-1]).replace("_", " ")
        params = urllib.parse.urlencode(
            {
                "action": "query",
                "prop": "extracts",
                "explaintext": 1,
                "redirects": 1,
                "titles": title,
                "format": "json",
            }
        )
        request = urllib.request.Request(
            f"{self.api}?{params}", headers={"User-Agent": "youtube-no-face/0.1"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            pages = json.load(response)["query"]["pages"]
        page = next(iter(pages.values()))
        return page.get("extract", "")


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


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
        },
        ["topic", "queries"],
    )
    result = model.complete_json(
        "Generate precise, non-overlapping research queries. Cover causes, mechanisms, measurements, examples, and misconceptions.",
        f"Topic: {topic}",
        schema,
    )
    validate_non_empty_list(result, "queries")
    return result


def retrieve_sources(queries: dict[str, Any], backend: ResearchBackend, per_query: int = 2) -> dict[str, Any]:
    seen: set[str] = set()
    sources: list[dict[str, str]] = []
    for query in queries["queries"]:
        for result in backend.search(query, limit=per_query):
            if result["url"] in seen:
                continue
            seen.add(result["url"])
            sources.append({"query": query, **result})
    if not sources:
        raise ValueError("research returned no sources")
    return {"topic": queries["topic"], "sources": sources}


def clean_documents(sources: dict[str, Any], backend: ResearchBackend, max_chars: int = 12000) -> dict[str, Any]:
    documents = []
    for source in sources["sources"]:
        text = backend.fetch(source["url"])
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()[:max_chars]
        if len(text) < 200:
            continue
        documents.append({**source, "text": text})
    if not documents:
        raise ValueError("no usable source documents")
    return {"topic": sources["topic"], "documents": documents}


def extract_facts(documents: dict[str, Any], model: JsonModel) -> dict[str, Any]:
    fact_schema = _schema(
        {
            "claim": {"type": "string"},
            "evidence": {"type": "string"},
            "source_url": {"type": "string"},
            "source_title": {"type": "string"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
        ["claim", "evidence", "source_url", "source_title", "confidence"],
    )
    schema = _schema(
        {"facts": {"type": "array", "minItems": 4, "maxItems": 20, "items": fact_schema}},
        ["facts"],
    )
    compact = [
        {"title": d["title"], "url": d["url"], "text": d["text"]}
        for d in documents["documents"]
    ]
    result = model.complete_json(
        "Extract only claims explicitly supported by the supplied documents. Evidence must be a short paraphrase, not an invented quotation. Preserve the exact source URL.",
        json.dumps({"topic": documents["topic"], "documents": compact}),
        schema,
    )
    validate_non_empty_list(result, "facts")
    valid_urls = {d["url"] for d in documents["documents"]}
    for fact in result["facts"]:
        if fact["source_url"] not in valid_urls:
            raise ValueError("fact cites a source that was not retrieved")
    return {"topic": documents["topic"], **result}


def deduplicate_facts(facts: dict[str, Any], model: JsonModel) -> dict[str, Any]:
    item_schema = _schema(
        {
            "id": {"type": "string"},
            "claim": {"type": "string"},
            "source_urls": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
        ["id", "claim", "source_urls", "confidence"],
    )
    schema = _schema(
        {
            "facts": {"type": "array", "minItems": 3, "maxItems": 12, "items": item_schema},
            "conflicts": {"type": "array", "items": {"type": "string"}},
        },
        ["facts", "conflicts"],
    )
    result = model.complete_json(
        "Merge equivalent facts, retain source provenance, and report genuine contradictions. Do not add new claims.",
        json.dumps(facts),
        schema,
    )
    validate_non_empty_list(result, "facts")
    return {"topic": facts["topic"], **result}


def plan_script(knowledge: dict[str, Any], model: JsonModel) -> dict[str, Any]:
    beat_schema = _schema(
        {
            "purpose": {"type": "string"},
            "fact_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "visual_intent": {"type": "string"},
        },
        ["purpose", "fact_ids", "visual_intent"],
    )
    schema = _schema(
        {
            "angle": {"type": "string"},
            "beats": {"type": "array", "minItems": 4, "maxItems": 7, "items": beat_schema},
        },
        ["angle", "beats"],
    )
    result = model.complete_json(
        "Plan a clear 45-60 second explainer. Start with a concrete tension or counterintuitive fact. Use only supplied fact IDs. Include one example and a concise takeaway.",
        json.dumps(knowledge),
        schema,
    )
    return {"topic": knowledge["topic"], **result}


def write_script(knowledge: dict[str, Any], plan: dict[str, Any], model: JsonModel) -> dict[str, Any]:
    segment_schema = _schema(
        {
            "narration": {"type": "string"},
            "visual_query": {"type": "string"},
            "fact_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        },
        ["narration", "visual_query", "fact_ids"],
    )
    schema = _schema(
        {
            "topic": {"type": "string"},
            "hook": {"type": "string"},
            "segments": {"type": "array", "minItems": 4, "maxItems": 7, "items": segment_schema},
            "cta": {"type": "string"},
        },
        ["topic", "hook", "segments", "cta"],
    )
    result = model.complete_json(
        "Write natural spoken English for a curious adult. Target 110-150 total spoken words. Use short varied sentences. Avoid 'the surprising reason', 'hidden secret', generic hype, repeated topic wording, and corporate prose. Every factual sentence must map to supplied fact IDs. CTA may be empty.",
        json.dumps({"knowledge": knowledge, "plan": plan}),
        schema,
    )
    return result


def validate_final_script(script: dict[str, Any], knowledge: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    fact_ids = {fact["id"] for fact in knowledge["facts"]}
    used_ids: set[str] = set()
    if script.get("topic", "").strip() != knowledge["topic"].strip():
        errors.append("script topic does not match requested topic")
    segments = script.get("segments")
    if not isinstance(segments, list) or not segments:
        errors.append("segments must be non-empty")
        segments = []
    spoken = [script.get("hook", ""), script.get("cta", "")]
    banned = ("the surprising reason", "hidden secret", "hidden engineering problem")
    for index, segment in enumerate(segments):
        narration = segment.get("narration", "")
        visual = segment.get("visual_query", "")
        ids = segment.get("fact_ids", [])
        spoken.append(narration)
        if not narration.strip() or not visual.strip():
            errors.append(f"segment {index} has empty narration or visual query")
        unknown = set(ids).difference(fact_ids)
        if unknown:
            errors.append(f"segment {index} uses unknown fact IDs: {sorted(unknown)}")
        used_ids.update(ids)
    text = " ".join(spoken).strip()
    words = re.findall(r"\b[\w'-]+\b", text)
    if not 90 <= len(words) <= 170:
        errors.append(f"spoken word count {len(words)} is outside 90-170")
    lowered = text.lower()
    for phrase in banned:
        if phrase in lowered:
            errors.append(f"banned generic phrase: {phrase}")
    if not used_ids:
        errors.append("script uses no researched facts")
    return {
        "valid": not errors,
        "errors": errors,
        "word_count": len(words),
        "used_fact_ids": sorted(used_ids),
        "source_urls": sorted({url for fact in knowledge["facts"] if fact["id"] in used_ids for url in fact["source_urls"]}),
    }


@dataclass
class ContentPipeline:
    model: JsonModel
    research: ResearchBackend

    def run(self, topic: str) -> dict[str, dict[str, Any]]:
        artifacts: dict[str, dict[str, Any]] = {}
        artifacts["01_queries"] = plan_queries(topic, self.model)
        artifacts["02_sources"] = retrieve_sources(artifacts["01_queries"], self.research)
        artifacts["03_documents"] = clean_documents(artifacts["02_sources"], self.research)
        artifacts["04_facts"] = extract_facts(artifacts["03_documents"], self.model)
        artifacts["05_knowledge"] = deduplicate_facts(artifacts["04_facts"], self.model)
        artifacts["06_plan"] = plan_script(artifacts["05_knowledge"], self.model)
        artifacts["07_script"] = write_script(artifacts["05_knowledge"], artifacts["06_plan"], self.model)
        artifacts["08_validation"] = validate_final_script(artifacts["07_script"], artifacts["05_knowledge"])
        if not artifacts["08_validation"]["valid"]:
            raise ValueError("script validation failed: " + "; ".join(artifacts["08_validation"]["errors"]))
        return artifacts
