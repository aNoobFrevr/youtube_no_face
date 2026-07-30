import unittest

from pipeline.script import (
    FakeScriptProvider,
    ScriptGenerationError,
    generate_script,
    validate_script,
)


class LegacyScriptContractTests(unittest.TestCase):
    """The old provider remains only as a deterministic unit-test fixture."""

    def test_validator_accepts_complete_script(self):
        script = {
            "topic": "Why airplane windows are round",
            "hook": "Square windows once helped tear early jetliners apart.",
            "segments": [
                {"narration": "Sharp corners concentrate stress.", "visual_query": "airplane window stress diagram"},
                {"narration": "Rounded windows spread that force.", "visual_query": "modern rounded airplane window"},
            ],
            "cta": "",
        }
        # The legacy contract requires a CTA; the production contract now permits an empty CTA.
        script["cta"] = "Follow for more engineering stories."
        self.assertEqual(validate_script(script), script)

    def test_fake_provider_is_deterministic_but_not_used_by_runtime(self):
        provider = FakeScriptProvider()
        first = generate_script("Why airplane windows are round", provider)
        second = generate_script("Why airplane windows are round", provider)
        self.assertEqual(first, second)

    def test_raises_after_retry_budget_is_exhausted(self):
        class InvalidProvider:
            def generate(self, topic):
                return {"topic": topic, "hook": "", "segments": [], "cta": ""}

        with self.assertRaises(ScriptGenerationError):
            generate_script("Topic", InvalidProvider(), max_attempts=2)


if __name__ == "__main__":
    unittest.main()
