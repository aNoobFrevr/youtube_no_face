# Engineering Decisions

## ADR-001: Use an explicit staged pipeline

**Decision:** Represent research and script creation as eight explicit stages with persisted JSON artifacts.

**Reason:** Stage boundaries make failures inspectable, allow partial reruns, preserve provenance, and prevent a single opaque model call from controlling the entire product.

## ADR-002: Phone as control plane, GitHub Actions as execution plane

**Decision:** Use Android and Termux primarily to trigger and inspect work while GitHub Actions performs reproducible execution.

**Reason:** The user should not need a continuously running workstation, and heavier processing should not depend on the phone remaining active.

## ADR-003: Preserve relevance quality gates

**Decision:** Do not solve retrieval failures by simply lowering or removing the relevance threshold.

**Reason:** Weak sources would contaminate fact extraction and script generation. Improve the evidence available to ranking before relaxing acceptance criteria.

## ADR-004: Persist source provenance through fact extraction

**Decision:** Facts must remain associated with their supporting sources and excerpts.

**Reason:** Evidence-grounded scripts require traceability for validation, review, correction, and eventual citation workflows.

## ADR-005: Bound model inputs

**Decision:** Limit candidate counts, excerpt lengths, and prompt payloads sent to model providers.

**Reason:** GitHub Models has rejected oversized requests with HTTP 413. Bounded inputs improve reliability, latency, and cost control.

## ADR-006: Deterministic fixtures must satisfy production contracts

**Decision:** Tests may replace nondeterministic services, but their outputs must still satisfy production schemas and validators.

**Reason:** Fixtures that bypass real constraints produce misleading failures or false confidence.

## ADR-007: Verify connector writes

**Decision:** A connector-reported commit SHA is not enough to mark a task complete. Verify the resulting file or commit diff.

**Reason:** Earlier operations appeared successful without verified intended changes. Repository state is the source of truth.

## ADR-008: Documentation is part of the implementation

**Decision:** Update requirements, progress, known issues, decisions, roadmap, and handoff notes alongside material code changes.

**Reason:** This allows work to resume without reconstructing project history from chat sessions.
