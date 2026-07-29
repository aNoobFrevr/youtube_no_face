# Stage 01: script generation

Stage 01 converts a topic into validated `script.json` data.

The output contract requires:

- `topic`: the requested topic
- `hook`: a non-empty opening line
- `segments`: one or more narration and visual-query pairs
- `cta`: a non-empty closing line

Generation is provider-driven and retried when validation fails. CI and the current workflow use `FakeScriptProvider`, which is deterministic and performs no network access. A real model provider will be added behind the same interface after its credentials, cost controls, and response parsing have their own tests.
