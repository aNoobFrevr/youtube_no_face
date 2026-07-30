# Roadmap

## Completed foundation

- [x] Eight-stage research-to-script architecture.
- [x] Stage-specific JSON artifacts.
- [x] Query planning.
- [x] Source retrieval with model-based relevance ranking.
- [x] Document cleaning.
- [x] Evidence-backed fact extraction.
- [x] Fact deduplication and knowledge consolidation.
- [x] Content planning.
- [x] Script generation.
- [x] Script and artifact validation.
- [x] Ability to start a workflow from a selected stage.
- [x] Resilient handling for Wikipedia rate limiting.
- [x] Prompt-size reductions for GitHub Models requests.

## Current stabilization work

- [ ] Improve retrieval recall without removing the relevance quality gate.
- [ ] Search multiple query variants and deduplicate candidate URLs.
- [ ] Fetch excerpts before final rejection when snippets are inconclusive.
- [ ] Add deterministic tests for low-snippet/high-content relevance cases.
- [ ] Verify all deterministic fixtures satisfy production validation contracts.
- [ ] Make workflow failures easier to diagnose from compact logs and artifacts.

## Development workflow

- [ ] Trigger CI automatically for relevant pushes to the development branch.
- [ ] Establish a reliable edit, commit, push, inspect, and repair loop.
- [ ] Add fast stage-level tests that run before full end-to-end execution.
- [ ] Cache valid upstream artifacts where safe.
- [ ] Keep project documentation synchronized with code changes.

## Product expansion

- [ ] Human review and feedback interface.
- [ ] Revision loop for research, plan, and script feedback.
- [ ] Narration generation.
- [ ] Scene and visual planning.
- [ ] Image or footage generation and retrieval.
- [ ] Automated video assembly.
- [ ] Thumbnail generation.
- [ ] Publishing and metadata automation.
- [ ] Post-publication analytics and learning loop.

## Definition of the next milestone

The immediate milestone is a consistently green research-to-script workflow across a representative topic suite, including topics whose useful sources are not obvious from search snippets alone.
