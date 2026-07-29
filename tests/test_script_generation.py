import json
import tempfile
import unittest
from pathlib import Path

from pipeline.context import RunContext
from pipeline.script import (
    FakeScriptProvider,
    ScriptGenerationError,
    generate_script,
    validate_script,
)


class ScriptValidationTests(unittest.TestCase):
    def test_accepts_complete_short_script(self):
        script = {
            "topic": "Why airplane windows are round",
            "hook": "Square windows once helped tear early jetliners apart.",
            "segments": [
                {
                    "narration": "Sharp corners concentrate stress when a cabin is pressurized.",
                    "visual_query": "airplane window stress diagram",
                },
                {
                    "narration": "Rounded windows spread that force smoothly around the frame.",
                    "visual_query": "modern rounded airplane window",
                },
            ],
            "cta": "Follow for more engineering stories.",
        }
        self.assertEqual(validate_script(script), script)

    def test_rejects_empty_segments(self):
        with self.assertRaises(ValueError):
            validate_script(
                {
                    "topic": "Topic",
                    "hook": "Hook",
                    "segments": [],
                    "cta": "CTA",
                }
            )


class ScriptGenerationTests(unittest.TestCase):
    def test_fake_provider_is_deterministic(self):
        provider = FakeScriptProvider()
        first = generate_script("Why airplane windows are round", provider)
        second = generate_script("Why airplane windows are round", provider)
        self.assertEqual(first, second)
        self.assertGreaterEqual(len(first["segments"]), 2)

    def test_retries_invalid_provider_output(self):
        responses = [
            {"topic": "Topic", "hook": "Hook", "segments": [], "cta": "CTA"},
            {
                "topic": "Topic",
                "hook": "A valid hook",
                "segments": [
                    {"narration": "A valid segment", "visual_query": "valid visual"}
                ],
                "cta": "A valid CTA",
            },
        ]

        class SequencedProvider:
            def generate(self, topic):
                return responses.pop(0)

        result = generate_script("Topic", SequencedProvider(), max_attempts=2)
        self.assertEqual(result["hook"], "A valid hook")

    def test_raises_after_retry_budget_is_exhausted(self):
        class InvalidProvider:
            def generate(self, topic):
                return {"topic": topic, "hook": "", "segments": [], "cta": ""}

        with self.assertRaises(ScriptGenerationError):
            generate_script("Topic", InvalidProvider(), max_attempts=2)

    def test_stage_writes_valid_script_json(self):
        from pipeline.run import stage_script

        with tempfile.TemporaryDirectory() as tmp:
            context = RunContext.create(Path(tmp), "Why airplane windows are round", "run-1")
            stage_script(context)
            payload = json.loads((context.run_dir / "script.json").read_text())
            validate_script(payload)
            self.assertGreaterEqual(len(payload["segments"]), 2)


if __name__ == "__main__":
    unittest.main()
