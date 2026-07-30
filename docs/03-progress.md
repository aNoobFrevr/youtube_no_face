# Progress Log

## 2026-07-30

### Completed

- Established the eight-stage research pipeline and stage artifact contract.
- Added query planning, retrieval, cleaning, fact extraction, deduplication, planning, script generation, and validation stages.
- Added resilient Wikipedia handling after rate-limit failures.
- Reduced model prompt payloads after GitHub Models rejected oversized requests.
- Added deterministic tests for the pipeline.
- Diagnosed a deterministic fixture failure caused by a 73-word script violating the configured 90–170 spoken-word range.
- Diagnosed workflow run `30477255825`, job `90661976400`.
- Identified the active production blocker: retrieval rejects all candidates when the top model-ranked result scores below the configured relevance threshold.
- Started repository documentation under `docs/`.

### Current blocker

The topic `Why is gravity different in different places` fails during retrieval for the query:

> What causes variations in gravity across Earth's surface?

The current implementation ranks search candidates from titles and snippets and raises an exception when the highest score is below the threshold, currently 65. This can reject potentially useful pages before their content is inspected.

### Proposed repair

- Search the original query and a topic-qualified variant.
- Deduplicate candidates by normalized URL.
- Rank initial candidates from metadata.
- When metadata scores are insufficient, fetch bounded excerpts from promising candidates.
- Rerank using those excerpts.
- Preserve the threshold as a quality gate after richer evidence is available.
- Add deterministic coverage for this fallback path.

### Verification note

Previous connector operations returned commit identifiers for proposed retrieval work, but the actual file changes were not verified. Those commits must not be treated as containing the intended implementation until repository contents or commit diffs confirm it.

## Update policy

Add an entry after each meaningful implementation, diagnosis, workflow result, or architectural decision. Include exact workflow identifiers and commit hashes where they materially help continuation.
