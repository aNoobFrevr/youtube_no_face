from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pipeline.content_pipeline as content_pipeline
from pipeline.content_pipeline import ContentPipeline, GitHubModelsClient, JsonModel
from pipeline.context import RunContext
from pipeline.research import ResilientWikipediaResearchBackend
from pipeline.robust_retrieval import retrieve_sources_evidence_first


def extract_facts_query_aware(documents: dict[str, Any], model: JsonModel) -> dict[str, Any]:
    """Validate facts against the exact (query_id, source_url) document.

    The same source can legitimately answer several research queries. Indexing
    documents by URL alone collapses those query-specific records and causes a
    false query-id mismatch when the model cites the shared source.
    """
    fact_schema = content_pipeline._schema(
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
    schema = content_pipeline._schema(
        {"facts": {"type": "array", "minItems": 4, "maxItems": 24, "items": fact_schema}},
        ["facts"],
    )
    compact = [
        {
            "query_id": document["query_id"],
            "query": document["query"],
            "title": document["title"],
            "url": document["url"],
            "text": document["text"],
        }
        for document in documents["documents"]
    ]
    result = model.complete_json(
        "Extract only atomic claims directly entailed by the supplied text. "
        "Copy a short exact evidence excerpt from the source text. Preserve the "
        "query_id belonging to the document from which each fact was extracted, "
        "even when multiple documents share the same URL. Produce at least one "
        "fact for every query_id.",
        json.dumps(
            {
                "topic": documents["topic"],
                "required_concepts": documents["required_concepts"],
                "documents": compact,
            }
        ),
        schema,
    )
    content_pipeline.validate_non_empty_list(result, "facts")

    docs_by_query_and_url = {
        (document["query_id"], document["url"]): document
        for document in documents["documents"]
    }
    retrieved_urls = {document["url"] for document in documents["documents"]}
    expected_queries = {document["query_id"] for document in documents["documents"]}
    covered_queries: set[str] = set()

    for fact in result["facts"]:
        if fact["source_url"] not in retrieved_urls:
            raise ValueError("fact cites a source that was not retrieved")
        doc = docs_by_query_and_url.get((fact["query_id"], fact["source_url"]))
        if doc is None:
            raise ValueError("fact query_id does not match its source document")
        excerpt = content_pipeline._normalise(fact["evidence_excerpt"])
        if not excerpt or excerpt not in content_pipeline._normalise(doc["text"]):
            raise ValueError("fact evidence excerpt is not present in its source document")
        covered_queries.add(fact["query_id"])

    if covered_queries != expected_queries:
        raise ValueError(f"fact extraction missed queries: {sorted(expected_queries - covered_queries)}")
    return {
        "topic": documents["topic"],
        "required_concepts": documents["required_concepts"],
        **result,
    }


# ContentPipeline resolves these stages from module globals. Install the
# production implementations while retaining the public pipeline API.
content_pipeline.retrieve_sources = retrieve_sources_evidence_first
content_pipeline.extract_facts = extract_facts_query_aware


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the eight-stage research pipeline")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"))
    return parser.parse_args()


def persist_artifacts(context: RunContext, artifacts: dict[str, dict]) -> None:
    for name, payload in artifacts.items():
        (context.run_dir / f"{name}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    manifest = {
        "run_id": context.run_id,
        "topic": context.topic,
        "mode": "eight-stage-research-pipeline",
        "artifacts": [f"{name}.json" for name in artifacts],
        "validation": artifacts["08_validation"],
    }
    context.manifest_file.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    context.status_file.write_text("completed\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    context = RunContext.create(args.runs_dir, args.topic, args.run_id)
    print(f"RUN_ID={context.run_id}")

    try:
        pipeline = ContentPipeline(
            model=GitHubModelsClient(),
            research=ResilientWikipediaResearchBackend(),
        )
        artifacts = pipeline.run(context.topic)
        persist_artifacts(context, artifacts)
    except Exception:
        context.status_file.write_text("failed\n", encoding="utf-8")
        raise

    print(f"RUN_DIR={context.run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
