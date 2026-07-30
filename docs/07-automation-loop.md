# Autonomous Iteration Loop

## Goal

Reduce manual intervention while repairing the pipeline by coupling repository changes to CI execution and using workflow results as the next diagnostic input.

## Desired loop

```text
edit
commit
push
GitHub Actions runs
inspect status and logs
repair
repeat until green
```

## Current limitation

Interactive ChatGPT turns are not a continuously running process. A persistent external orchestrator is required to wait, poll, and reinvoke a model after workflow completion.

## Repository-side improvements

- Trigger the development workflow on pushes to `agent/eight-stage-research-pipeline`.
- Keep deterministic tests early in the job so failures arrive quickly.
- Upload stage artifacts and compact diagnostic summaries even on failure.
- Make failures identify the stage, query, candidate scores, and relevant artifact paths.
- Avoid rerunning completed stages when valid artifacts can be safely reused.

## Future orchestrator

A lightweight process running through OpenCode, Codex CLI, or the OpenAI API can:

1. Modify the repository.
2. Run local fast tests where available.
3. Commit and push.
4. Poll the GitHub Actions run associated with the commit.
5. Download logs and artifacts.
6. Invoke the model with the failure context.
7. Repeat until the acceptance criteria pass or a safety limit is reached.

The orchestrator, rather than the model request itself, owns waiting, retries, maximum iterations, and termination.
