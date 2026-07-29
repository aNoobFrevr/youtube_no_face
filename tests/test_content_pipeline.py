import unittest

from pipeline.content_pipeline import ContentPipeline, validate_final_script


class FakeResearchBackend:
    def search(self, query, limit=3):
        return [
            {"title": "Gravity of Earth", "url": "https://example.test/gravity"},
            {"title": "Earth rotation", "url": "https://example.test/rotation"},
        ][:limit]

    def fetch(self, url):
        if url.endswith("gravity"):
            return ("Earth's effective gravity varies with latitude, altitude, and local mass distribution. " * 20)
        return ("Earth's rotation creates a centrifugal effect that is strongest near the equator. " * 20)


class FakeJsonModel:
    def __init__(self):
        self.calls = 0

    def complete_json(self, system, user, schema):
        self.calls += 1
        if self.calls == 1:
            return {
                "topic": "Why is gravity different in different places",
                "queries": [
                    "gravity variation by latitude",
                    "altitude and gravitational acceleration",
                    "Earth rotation effective gravity",
                    "local gravity anomalies mass distribution",
                ],
            }
        if self.calls == 2:
            return {
                "facts": [
                    {
                        "claim": "Effective gravity is lower near the equator than near the poles.",
                        "evidence": "Latitude changes the measured effective acceleration.",
                        "source_url": "https://example.test/gravity",
                        "source_title": "Gravity of Earth",
                        "confidence": "high",
                    },
                    {
                        "claim": "Earth's rotation reduces effective gravity most strongly near the equator.",
                        "evidence": "The centrifugal effect is strongest near the equator.",
                        "source_url": "https://example.test/rotation",
                        "source_title": "Earth rotation",
                        "confidence": "high",
                    },
                    {
                        "claim": "Gravity decreases with altitude.",
                        "evidence": "Distance from Earth's centre affects gravitational acceleration.",
                        "source_url": "https://example.test/gravity",
                        "source_title": "Gravity of Earth",
                        "confidence": "high",
                    },
                    {
                        "claim": "Local geology can produce small gravity anomalies.",
                        "evidence": "Local mass distribution changes measured gravity.",
                        "source_url": "https://example.test/gravity",
                        "source_title": "Gravity of Earth",
                        "confidence": "medium",
                    },
                ]
            }
        if self.calls == 3:
            return {
                "facts": [
                    {"id": "F1", "claim": "Gravity is weaker near the equator.", "source_urls": ["https://example.test/gravity", "https://example.test/rotation"], "confidence": "high"},
                    {"id": "F2", "claim": "Gravity decreases with altitude.", "source_urls": ["https://example.test/gravity"], "confidence": "high"},
                    {"id": "F3", "claim": "Local geology creates small anomalies.", "source_urls": ["https://example.test/gravity"], "confidence": "medium"},
                ],
                "conflicts": [],
            }
        if self.calls == 4:
            return {
                "angle": "Your weight changes slightly as you move around Earth.",
                "beats": [
                    {"purpose": "hook", "fact_ids": ["F1"], "visual_intent": "person on globe"},
                    {"purpose": "rotation", "fact_ids": ["F1"], "visual_intent": "rotating Earth"},
                    {"purpose": "altitude", "fact_ids": ["F2"], "visual_intent": "mountain height"},
                    {"purpose": "geology", "fact_ids": ["F3"], "visual_intent": "density map"},
                ],
            }
        return {
            "topic": "Why is gravity different in different places",
            "hook": "You do not weigh exactly the same everywhere on Earth.",
            "segments": [
                {"narration": "Near the equator, effective gravity is slightly weaker than it is near the poles.", "visual_query": "Earth equator poles gravity comparison", "fact_ids": ["F1"]},
                {"narration": "Part of that difference comes from rotation. The equator moves fastest, so the outward centrifugal effect is strongest there.", "visual_query": "rotating Earth centrifugal effect equator", "fact_ids": ["F1"]},
                {"narration": "Altitude matters too. A mountain puts you farther from Earth's centre, reducing gravitational pull by a small amount.", "visual_query": "mountain altitude Earth center diagram", "fact_ids": ["F2"]},
                {"narration": "Even the rock below you matters. Dense ore bodies and underground structures create tiny local gravity anomalies that instruments can map.", "visual_query": "geological gravity anomaly map", "fact_ids": ["F3"]},
                {"narration": "So gravity is not one perfectly fixed number. Latitude, height, rotation, and local geology all shift it slightly.", "visual_query": "Earth gravity variation map", "fact_ids": ["F1", "F2", "F3"]},
            ],
            "cta": "",
        }


class ContentPipelineTests(unittest.TestCase):
    def test_pipeline_emits_all_eight_artifacts(self):
        pipeline = ContentPipeline(FakeJsonModel(), FakeResearchBackend())
        artifacts = pipeline.run("Why is gravity different in different places")
        self.assertEqual(
            list(artifacts),
            ["01_queries", "02_sources", "03_documents", "04_facts", "05_knowledge", "06_plan", "07_script", "08_validation"],
        )
        self.assertTrue(artifacts["08_validation"]["valid"])
        self.assertGreaterEqual(len(artifacts["08_validation"]["source_urls"]), 2)

    def test_validator_rejects_generic_template_language(self):
        knowledge = {
            "topic": "Topic",
            "facts": [{"id": "F1", "claim": "Claim", "source_urls": ["https://example.test"], "confidence": "high"}],
        }
        script = {
            "topic": "Topic",
            "hook": "The surprising reason starts here.",
            "segments": [{"narration": "word " * 100, "visual_query": "visual", "fact_ids": ["F1"]}],
            "cta": "",
        }
        report = validate_final_script(script, knowledge)
        self.assertFalse(report["valid"])
        self.assertTrue(any("banned generic phrase" in error for error in report["errors"]))

    def test_validator_rejects_unknown_fact_ids(self):
        knowledge = {
            "topic": "Topic",
            "facts": [{"id": "F1", "claim": "Claim", "source_urls": ["https://example.test"], "confidence": "high"}],
        }
        script = {
            "topic": "Topic",
            "hook": "A concrete hook about this topic.",
            "segments": [{"narration": "word " * 100, "visual_query": "visual", "fact_ids": ["F9"]}],
            "cta": "",
        }
        report = validate_final_script(script, knowledge)
        self.assertFalse(report["valid"])
        self.assertTrue(any("unknown fact IDs" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
