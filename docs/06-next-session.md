# Next Session Handoff

## Repository state

- Repository: `aNoobFrevr/youtube_no_face`
- Working branch: `agent/eight-stage-research-pipeline`
- Pipeline entry point: `pipeline/content_pipeline.py`
- Workflow: `generate.yml`

## Current objective

Make the eight-stage workflow complete successfully for:

```text
Why is gravity different in different places
```

## Current blocker

Stage 2 source retrieval fails because no candidate reaches the configured relevance threshold for:

```text
What causes variations in gravity across Earth's surface?
```

Relevant workflow identifiers:

- Run: `30477255825`
- Job: `90661976400`

## Exact next task

1. Inspect the current `retrieve_sources()` implementation and tests on the working branch.
2. Verify whether any previously proposed retrieval changes actually exist.
3. Implement multi-query candidate discovery using the original and topic-qualified query.
4. Normalize and deduplicate candidate URLs.
5. Retain metadata ranking as the fast path.
6. Fetch bounded excerpts for candidates when metadata ranking fails the threshold.
7. Rerank using title, snippet, and excerpt.
8. Apply the final quality threshold after excerpt reranking.
9. Add deterministic tests for both successful fallback and final rejection.
10. Commit, let Actions run, inspect the exact failure, and iterate.

## Likely files to change

- `pipeline/content_pipeline.py`
- Retrieval-related tests and fixtures
- `.github/workflows/generate.yml` if automatic branch CI is not already configured
- `docs/03-progress.md`
- `docs/04-known-issues.md`
- `docs/06-next-session.md`

## Guardrails

- Do not remove the relevance gate merely to make the workflow green.
- Do not assume earlier commit SHAs contain proposed fixes without inspecting their diffs.
- Keep fetched excerpts bounded to avoid HTTP 413 model requests.
- Preserve source attribution through all fallback ranking paths.
- Verify every repository write after committing.
