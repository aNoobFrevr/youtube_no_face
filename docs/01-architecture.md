# Architecture

## Operating model

The system is split into two planes:

- **Control plane:** Android and Termux are used to start runs, inspect results, and manage the repository.
- **Execution plane:** GitHub Actions runs the pipeline in a reproducible hosted environment.

## Eight-stage pipeline

| Stage | Responsibility | Artifact |
|---|---|---|
| 1 | Query planning | `01_queries.json` |
| 2 | Source retrieval and relevance ranking | `02_sources.json` |
| 3 | Document fetching and cleaning | `03_documents.json` |
| 4 | Atomic fact extraction with provenance | `04_facts.json` |
| 5 | Fact deduplication and knowledge consolidation | `05_knowledge.json` |
| 6 | Content planning | `06_plan.json` |
| 7 | Script generation | `07_script.json` |
| 8 | Structural and quality validation | `08_validation.json` |

Each artifact is intended to be inspectable and reusable. A run can resume from a selected stage when valid upstream artifacts already exist.

## Main implementation

The central pipeline implementation is in `pipeline/content_pipeline.py`. It coordinates stage execution, model calls, retrieval, artifact serialization, and validation.

The GitHub Actions workflow accepts at least:

- `topic`: the subject to research and script.
- `from_stage`: the first stage that should execute.

## Retrieval design

For each planned query, retrieval gathers candidates and asks a language model to rank them from metadata such as title and snippet. The top candidate must satisfy a configured relevance threshold before the source is accepted.

This quality gate prevents unrelated sources from contaminating later stages, but it can currently fail when search snippets are weak even when a useful source may exist.

## Reliability principles

- Intermediate state is written to stage artifacts.
- Validation failures are explicit rather than silently accepted.
- Research facts retain source provenance.
- Retrieval backends should handle rate limits and transient errors.
- Prompt payloads must be bounded to avoid provider request-size errors.
- Deterministic tests should use fixtures that satisfy the same contracts as production data.

## Intended evolution

The pipeline should remain modular so later components can consume `07_script.json` and research artifacts for narration, scene planning, visual generation, editing, thumbnails, review, and publishing.
