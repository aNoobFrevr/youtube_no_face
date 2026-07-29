from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ScriptProvider(Protocol):
    def generate(self, topic: str) -> dict[str, Any]:
        ...


@dataclass
class ScriptGenerationError(RuntimeError):
    topic: str
    attempts: int
    last_error: Exception

    def __str__(self) -> str:
        return (
            f"script generation failed for {self.topic!r} after "
            f"{self.attempts} attempts: {self.last_error}"
        )


def _require_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def validate_script(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("script must be a JSON object")

    required = {"topic", "hook", "segments", "cta"}
    missing = required.difference(payload)
    if missing:
        raise ValueError(f"script is missing fields: {', '.join(sorted(missing))}")

    _require_non_empty_string(payload["topic"], "topic")
    _require_non_empty_string(payload["hook"], "hook")
    _require_non_empty_string(payload["cta"], "cta")

    segments = payload["segments"]
    if not isinstance(segments, list) or not segments:
        raise ValueError("segments must be a non-empty list")

    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise ValueError(f"segments[{index}] must be an object")
        _require_non_empty_string(segment.get("narration"), f"segments[{index}].narration")
        _require_non_empty_string(segment.get("visual_query"), f"segments[{index}].visual_query")

    return payload


class FakeScriptProvider:
    """Deterministic provider used by CI and bootstrap runs.

    It deliberately performs no network access. A later provider can call an
    external model while retaining this provider for repeatable tests.
    """

    def generate(self, topic: str) -> dict[str, Any]:
        clean_topic = topic.strip()
        return {
            "topic": clean_topic,
            "hook": f"The surprising reason behind {clean_topic} starts with a hidden engineering problem.",
            "segments": [
                {
                    "narration": f"First, engineers studying {clean_topic} had to identify where force and failure accumulated.",
                    "visual_query": f"{clean_topic} engineering problem diagram",
                },
                {
                    "narration": "The final design spreads that force more evenly, reducing dangerous stress concentrations.",
                    "visual_query": f"{clean_topic} modern design close up",
                },
                {
                    "narration": "That small visible detail is therefore a safety feature shaped by hard-learned engineering lessons.",
                    "visual_query": f"{clean_topic} safety engineering explanation",
                },
            ],
            "cta": "Follow for more engineering stories hidden in everyday objects.",
        }


def generate_script(
    topic: str,
    provider: ScriptProvider,
    max_attempts: int = 3,
) -> dict[str, Any]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    last_error: Exception = ValueError("provider returned no result")
    for _attempt in range(1, max_attempts + 1):
        try:
            payload = provider.generate(topic)
            validated = validate_script(payload)
            if validated["topic"].strip() != topic.strip():
                raise ValueError("generated script topic does not match requested topic")
            return validated
        except Exception as exc:
            last_error = exc

    raise ScriptGenerationError(topic, max_attempts, last_error)
