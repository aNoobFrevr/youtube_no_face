# Original Requirements

## Product vision

Build a phone-first, faceless YouTube content pipeline that can take a topic and produce a researched, evidence-grounded script through a repeatable multi-stage workflow.

The phone acts as the control plane. GitHub Actions acts as the execution plane for heavier work and reproducible runs.

## Core requirements

- Accept a topic as the primary input.
- Research the topic using multiple sources rather than relying on a single page.
- Preserve evidence excerpts and source attribution through the pipeline.
- Separate research, planning, writing, and validation into explicit stages.
- Produce deterministic, inspectable intermediate artifacts.
- Support restarting from a selected stage without rerunning all prior stages.
- Keep operating cost at or near zero where practical.
- Allow quality gates to reject weak evidence or invalid scripts.
- Support future human feedback loops for review and refinement.

## Constraints

- Primary operator environment: Android with Termux.
- Repository and CI: GitHub and GitHub Actions.
- Development branch: `agent/eight-stage-research-pipeline`.
- The system should remain usable without a continuously running local workstation.
- Large language model prompts must stay within provider request-size limits.
- External retrieval must tolerate rate limits and transient network failures.

## Current success criteria

A successful pipeline run should:

1. Generate useful research queries from the topic.
2. Retrieve sufficiently relevant and diverse sources.
3. Clean documents into usable text.
4. Extract atomic, source-backed facts.
5. Deduplicate overlapping facts while retaining provenance.
6. Create a coherent content plan.
7. Generate a script within the configured format and spoken-length constraints.
8. Validate structure, evidence coverage, and output quality.

## Longer-term direction

The research-and-script pipeline is the foundation for a broader no-face publishing system that may later include review UI, narration, visual generation, thumbnail generation, video assembly, and publishing automation.
