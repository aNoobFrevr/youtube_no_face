import unittest

from pipeline.content_pipeline import ContentPipeline, retrieve_sources, validate_final_script

TOPIC = "Why is gravity different in different places"


class FakeResearchBackend:
    def search(self, query, limit=3):
        slug = query.split()[0].lower()
        return [
            {"title": f"Relevant {query}", "url": f"https://science.test/{slug}", "snippet": "directly relevant scientific article"},
            {"title": "The Culture", "url": f"https://irrelevant.test/{slug}", "snippet": "fictional society"},
            {"title": "Unrelated topic", "url": f"https://other.test/{slug}", "snippet": "not about gravity"},
        ][:limit]

    def fetch(self, url):
        slug = url.rsplit("/", 1)[-1]
        excerpts = {
            "latitude": "Effective gravity is lower near the equator than near the poles.",
            "altitude": "Gravitational acceleration decreases as distance from Earth's centre increases.",
            "rotation": "Earth's rotation creates a centrifugal effect strongest near the equator.",
            "local": "Dense underground structures can produce small local gravity anomalies.",
        }
        return (excerpts[slug] + " Measurement and geophysical context are included. ") * 20


class FakeJsonModel:
    def __init__(self):
        self.calls = 0

    def complete_json(self, system, user, schema):
        self.calls += 1
        if self.calls == 1:
            return {
                "topic": TOPIC,
                "queries": ["latitude gravity", "altitude gravity", "rotation gravity", "local gravity anomalies"],
                "required_concepts": ["latitude", "altitude", "rotation", "local geology"],
            }
        if self.calls == 2:
            return {
                "rankings": [
                    {
                        "candidate_id": f"C{i}",
                        "score": 95 if (i - 1) % 3 == 0 else 5,
                        "reason": "direct match" if (i - 1) % 3 == 0 else "irrelevant",
                    }
                    for i in range(1, 13)
                ]
            }
        if self.calls == 3:
            return {
                "facts": [
                    {"query_id": "Q1", "claim": "Effective gravity is lower near the equator than near the poles.", "evidence_excerpt": "Effective gravity is lower near the equator than near the poles.", "source_url": "https://science.test/latitude", "source_title": "Relevant latitude gravity", "confidence": "high"},
                    {"query_id": "Q2", "claim": "Gravity decreases with altitude.", "evidence_excerpt": "Gravitational acceleration decreases as distance from Earth's centre increases.", "source_url": "https://science.test/altitude", "source_title": "Relevant altitude gravity", "confidence": "high"},
                    {"query_id": "Q3", "claim": "Rotation reduces effective gravity most strongly near the equator.", "evidence_excerpt": "Earth's rotation creates a centrifugal effect strongest near the equator.", "source_url": "https://science.test/rotation", "source_title": "Relevant rotation gravity", "confidence": "high"},
                    {"query_id": "Q4", "claim": "Dense underground structures create local gravity anomalies.", "evidence_excerpt": "Dense underground structures can produce small local gravity anomalies.", "source_url": "https://science.test/local", "source_title": "Relevant local gravity anomalies", "confidence": "medium"},
                ]
            }
        if self.calls == 4:
            return {
                "facts": [
                    {"id": "F1", "claim": "Effective gravity is lower near the equator than near the poles.", "query_ids": ["Q1"], "source_urls": ["https://science.test/latitude"], "evidence_excerpts": ["Effective gravity is lower near the equator than near the poles."], "confidence": "high"},
                    {"id": "F2", "claim": "Gravity decreases with altitude.", "query_ids": ["Q2"], "source_urls": ["https://science.test/altitude"], "evidence_excerpts": ["Gravitational acceleration decreases as distance from Earth's centre increases."], "confidence": "high"},
                    {"id": "F3", "claim": "Rotation reduces effective gravity most strongly near the equator.", "query_ids": ["Q3"], "source_urls": ["https://science.test/rotation"], "evidence_excerpts": ["Earth's rotation creates a centrifugal effect strongest near the equator."], "confidence": "high"},
                    {"id": "F4", "claim": "Dense underground structures create local gravity anomalies.", "query_ids": ["Q4"], "source_urls": ["https://science.test/local"], "evidence_excerpts": ["Dense underground structures can produce small local gravity anomalies."], "confidence": "medium"},
                ],
                "conflicts": [],
            }
        if self.calls == 5:
            return {
                "angle": "Your weight changes slightly around Earth.",
                "beats": [
                    {"purpose": "latitude", "fact_ids": ["F1"], "visual_intent": "equator and poles"},
                    {"purpose": "altitude", "fact_ids": ["F2"], "visual_intent": "mountain"},
                    {"purpose": "rotation", "fact_ids": ["F3"], "visual_intent": "rotating Earth"},
                    {"purpose": "geology", "fact_ids": ["F4"], "visual_intent": "gravity anomaly map"},
                ],
            }
        return {
            "topic": TOPIC,
            "hook": "You do not weigh exactly the same everywhere on Earth.",
            "segments": [
                {"narration": "Effective gravity is lower near the equator than near the poles because Earth is not perfectly spherical.", "visual_query": "equator poles gravity", "fact_ids": ["F1"]},
                {"narration": "Gravity also decreases as you move farther from Earth's centre, so altitude matters even when the change is small.", "visual_query": "mountain Earth centre", "fact_ids": ["F2"]},
                {"narration": "Rotation adds another effect. Its centrifugal influence is strongest near the equator and reduces effective gravity there.", "visual_query": "rotating Earth equator", "fact_ids": ["F3"]},
                {"narration": "Dense underground structures can create small local gravity anomalies that geophysicists measure with sensitive instruments.", "visual_query": "underground density gravity map", "fact_ids": ["F4"]},
                {"narration": "Together, latitude, altitude, rotation, and local geology make gravity vary slightly from place to place across the planet.", "visual_query": "global gravity variation", "fact_ids": ["F1", "F2", "F3", "F4"]},
            ],
            "cta": "These differences are small, but precise measurements can map them and reveal what lies beneath Earth's surface.",
        }


class LowRelevanceModel:
    def complete_json(self, system, user, schema):
        return {"rankings": [{"candidate_id": "C1", "score": 20, "reason": "wrong subject"}]}


class ContentPipelineTests(unittest.TestCase):
    def test_pipeline_emits_all_eight_artifacts(self):
        artifacts = ContentPipeline(FakeJsonModel(), FakeResearchBackend()).run(TOPIC)
        self.assertEqual(list(artifacts), ["01_queries", "02_sources", "03_documents", "04_facts", "05_knowledge", "06_plan", "07_script", "08_validation"])
        self.assertTrue(artifacts["08_validation"]["valid"])
        self.assertEqual(artifacts["08_validation"]["query_coverage"], 1.0)
        self.assertEqual(artifacts["02_sources"]["candidates_considered"], 12)

    def test_retrieval_rejects_low_relevance_candidate(self):
        queries = {"topic": TOPIC, "queries": ["gravity measurement"], "required_concepts": ["measurement"]}
        with self.assertRaisesRegex(ValueError, "no sufficiently relevant source"):
            retrieve_sources(queries, FakeResearchBackend(), LowRelevanceModel(), per_query=1)

    def test_validator_rejects_generic_template_language(self):
        knowledge = {"topic": "Topic", "facts": [{"id": "F1", "claim": "Claim", "query_ids": ["Q1"], "source_urls": ["https://a.test"], "evidence_excerpts": ["Claim"], "confidence": "high"}]}
        script = {"topic": "Topic", "hook": "The surprising reason starts here.", "segments": [{"narration": "word " * 100, "visual_query": "visual", "fact_ids": ["F1"]}], "cta": ""}
        report = validate_final_script(script, knowledge)
        self.assertFalse(report["valid"])
        self.assertTrue(any("banned generic phrase" in error for error in report["errors"]))

    def test_validator_rejects_inadequate_query_coverage(self):
        knowledge = {
            "topic": "Topic",
            "facts": [
                {"id": "F1", "claim": "One", "query_ids": ["Q1"], "source_urls": ["https://a.test"], "evidence_excerpts": ["One"], "confidence": "high"},
                {"id": "F2", "claim": "Two", "query_ids": ["Q2"], "source_urls": ["https://b.test"], "evidence_excerpts": ["Two"], "confidence": "high"},
            ],
        }
        script = {"topic": "Topic", "hook": "A concrete hook.", "segments": [{"narration": "word " * 100, "visual_query": "visual", "fact_ids": ["F1"]}], "cta": ""}
        report = validate_final_script(script, knowledge)
        self.assertFalse(report["valid"])
        self.assertTrue(any("coverage" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
