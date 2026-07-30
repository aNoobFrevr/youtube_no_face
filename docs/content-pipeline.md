# Eight-stage researched content pipeline

The runtime no longer asks one model to invent a complete script from a topic. Each run produces inspectable artifacts and fails closed when provenance or quality checks fail.

1. `01_queries.json` — focused search queries covering mechanisms, measurements, examples, and misconceptions.
2. `02_sources.json` — deduplicated source metadata returned by the research backend.
3. `03_documents.json` — retrieved and cleaned source text.
4. `04_facts.json` — claims extracted only from retrieved documents, with evidence and exact source URLs.
5. `05_knowledge.json` — deduplicated facts, stable fact IDs, provenance, and conflicts.
6. `06_plan.json` — narrative beats mapped to fact IDs before prose is written.
7. `07_script.json` — natural narration, visual queries, and fact IDs for every segment.
8. `08_validation.json` — word count, source list, fact-ID checks, and style failures.

`script.json` remains as a compatibility copy of `07_script.json`.

## Provider boundaries

- `JsonModel` handles structured reasoning and writing. The first live adapter is `GitHubModelsClient`.
- `ResearchBackend` handles search and retrieval. The initial zero-key adapter uses Wikipedia's public API.
- Unit tests use deterministic fakes and never call a network service.

The Wikipedia adapter is intentionally an initial retrieval implementation, not the final research-quality target. It should later be supplemented with domain allowlists, official-source adapters, and a broader search provider. Later stages do not change when that replacement happens.

## GitHub Actions

The workflow grants only:

```yaml
permissions:
  contents: read
  models: read
```

GitHub Actions supplies the short-lived `GITHUB_TOKEN`. No additional model API key is required. The model is configurable through the workflow input and defaults to `openai/gpt-4.1`.

Pull requests run deterministic unit tests only. A manual `workflow_dispatch` performs live retrieval and GitHub Models inference.

## Failure policy

A production run fails rather than silently using the old generic fake script provider. Validation rejects:

- unknown fact IDs;
- citations to sources that were not retrieved;
- empty narration or visual queries;
- scripts outside the allowed spoken-word range;
- generic template phrases such as “the surprising reason” and “hidden secret”;
- scripts that use no researched facts.
