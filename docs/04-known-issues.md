# Known Issues

## KI-001: Retrieval rejects all candidates from weak snippets

**Status:** Open

**Observed in:** Workflow run `30477255825`, job `90661976400`.

**Failure:**

```text
ValueError: no sufficiently relevant source for query:
What causes variations in gravity across Earth's surface?
```

**Root cause:** `retrieve_sources()` ranks candidates from titles and snippets and immediately fails when the highest score is below the configured threshold. Search snippets may not expose the relevant passage even when the underlying article is useful.

**Planned fix:** Expand query variants, deduplicate candidates, fetch bounded excerpts for borderline candidates, rerank with article evidence, and only then apply the final relevance gate.

## KI-002: Deterministic fixture violated script length contract

**Status:** Diagnosed; verify fix in repository

**Observed in:** Workflow run `30476766068`.

**Failure:**

```text
ValueError: spoken word count 73 is outside 90-170
```

**Root cause:** The deterministic test fixture generated a script shorter than the production validator permits. This was a fixture problem rather than a production algorithm failure.

**Required verification:** Confirm the fixture now produces a valid 90–170 word script and that the deterministic suite passes.

## KI-003: Prior connector commits were not verified

**Status:** Open process issue

Some earlier write attempts returned commit SHAs without a verified file diff containing the intended retrieval changes.

**Impact:** Commit identifiers alone cannot be used as evidence that a fix exists.

**Rule:** After every connector write, verify the changed file or compare the resulting commit before recording the work as complete.

## KI-004: Manual workflow dispatch depends on phone connectivity

**Status:** Open

The Termux command to dispatch a workflow failed with an inability to connect to `api.github.com`.

**Impact:** The phone is an unreliable trigger when connectivity is intermittent.

**Direction:** Configure branch push triggers for development CI and use repository-connected tooling for commits where appropriate.

## KI-005: Node.js 20 deprecation warning in Actions

**Status:** Non-blocking

Workflow logs show a Node.js 20 deprecation warning from one or more actions. It did not cause the current pipeline failure.

**Direction:** Identify affected action versions and upgrade them separately from the retrieval repair.
