# Project Memory

This file is the durable, version-controlled memory for the `youtube_no_face` project. It records verified facts, explicit decisions, current constraints, and planned work so future contributors and AI agents do not have to reconstruct context from chat history.

## Verification policy

Every repository write must be followed by a read-back from the same branch or commit. Every assumption that can affect implementation must be converted into a verification step. Claims about workflows, commits, artifacts, tests, or repository state are not considered true until directly inspected.

## Repository and branch

- Repository: `aNoobFrevr/youtube_no_face`
- Active development branch: `agent/eight-stage-research-pipeline`
- Current operating model: the Android phone is the control plane; GitHub Actions is the execution plane.
- The repository README confirms that GitHub Actions runs tests, Python, model inference, asset acquisition, ffmpeg rendering, and artifact creation, while the phone is used only as a remote control.

## Current pipeline architecture

The research pipeline is organized as eight stages:

1. Query planning
2. Source retrieval
3. Cleaning
4. Fact extraction
5. Deduplication
6. Planning
7. Script generation
8. Validation

Expected stage artifacts:

- `01_queries.json`
- `02_sources.json`
- `03_documents.json`
- `04_facts.json`
- `05_knowledge.json`
- `06_plan.json`
- `07_script.json`
- `08_validation.json`

The pipeline uses deterministic run directories under `runs/<run_id>/` and supports ordered, resumable stage orchestration.

## Confirmed workflow state

The workflow file `.github/workflows/generate.yml` was read directly from the active branch and currently includes:

- automatic execution on pushes to `agent/eight-stage-research-pipeline`;
- pull-request execution targeting `main`;
- manual `workflow_dispatch` inputs for topic, starting stage, and model;
- a deterministic test job;
- a research smoke-test job;
- capture of pipeline output to `diagnostics/pipeline.log`;
- unconditional upload of `runs/` and `diagnostics/` using `if: always()`.

The GitHub connector was verified on 2026-07-30 by performing a complete create/read/delete/read cycle on a temporary repository file. The create and delete commits were returned by GitHub, the exact file content was read back, and the final read returned `404 Not Found`. Repository writes through the connector are therefore usable, but each write must still be individually verified.

## Known failure context

A previously observed retrieval failure was:

```text
ValueError: no sufficiently relevant source for query:
What causes variations in gravity across Earth's surface?
```

The associated retrieval behavior rejected a result when its top relevance score was below a threshold. Any proposed retrieval fix must be treated as unverified until its code, commit, tests, and workflow result are inspected.

Earlier issues included:

- Wikipedia HTTP 429 responses, addressed through a more resilient backend;
- GitHub Models HTTP 413 responses caused by prompt size, addressed by reducing prompt size;
- low-confidence retrieval results being rejected by the current ranking threshold.

These historical fixes should not be assumed to remain correct without regression tests.

## Strategic decision

The project will build an AI engineering platform before building an autonomous AI engineer.

### Phase 1: engineering infrastructure

Phase 1 should provide enough observability and reproducibility that a coding model can diagnose and iterate without the user manually copying logs, locating artifacts, or replaying steps.

Required capabilities:

- structured stage diagnostics;
- a run manifest;
- exception bundles;
- complete pipeline logging;
- deterministic replay from saved artifacts with no external API calls where feasible;
- regression fixtures for previously fixed failures;
- stable artifact layout;
- GitHub Actions summaries;
- automatically packaged debug bundles;
- tests for diagnostics, manifests, replay, and packaging.

Target run layout:

```text
runs/<run_id>/
    manifest.json
    pipeline.log
    metrics.json
    outputs/
    diagnostics/
        exception.txt
        traceback.txt
        environment.json
        timings.json
        llm_requests.json
        llm_responses.json
        summary.md
    debug_bundle.zip
```

The exact layout may be adapted to the existing codebase, but compatibility, deterministic naming, and machine readability are mandatory.

### Phase 2: AI engineer

After Phase 1 is complete, an AI engineer may consume diagnostics, replay failures, propose patches, run tests, inspect CI, and iterate. It must remain model-agnostic and must not depend on hidden chat state.

## Development policy

- Follow red -> green -> refactor.
- Add failing contract tests before new behavior where practical.
- Keep deterministic tests separate from integration or external-service tests.
- Never claim a fix is complete based only on code inspection.
- A change is complete only after affected files are read back, tests are observed, and relevant workflow output or artifacts are inspected.
- The repository is the canonical source of project memory; chat memory is only a convenience.

## Immediate next action

Implement Phase 1 on `agent/eight-stage-research-pipeline`, beginning with repository inspection and tests, then diagnostics/manifest infrastructure, replay support, workflow summaries, debug bundle packaging, and CI verification.
