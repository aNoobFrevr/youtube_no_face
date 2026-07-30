import unittest

from pipeline.robust_retrieval import retrieve_sources_evidence_first


class FakeResearchBackend:
    def __init__(self):
        self.documents = {
            "https://example.test/primary": (
                "This article directly explains the requested subject, its mechanism, "
                "measurement, historical context, and concrete examples. " * 20
            ),
            "https://example.test/secondary": (
                "This is a broad background article with partial context but less direct evidence. " * 20
            ),
        }

    def search(self, query, limit=3):
        return [
            {
                "title": f"Primary evidence for {query}",
                "url": "https://example.test/primary",
                "snippet": f"Direct explanation of {query}",
            },
            {
                "title": "Background reference",
                "url": "https://example.test/secondary",
                "snippet": "General background",
            },
        ][:limit]

    def fetch(self, url):
        return self.documents[url]


class ComparativeModel:
    def complete_json(self, system, user, schema):
        self.last_system = system
        self.last_user = user
        return {
            "selected_candidate_id": "C1",
            "reason": "The passage directly answers the exact research question.",
        }


class InvalidSelectionModel:
    def complete_json(self, system, user, schema):
        return {
            "selected_candidate_id": "not-a-candidate",
            "reason": "invalid test output",
        }


class RobustRetrievalTests(unittest.TestCase):
    def test_retrieval_is_not_tied_to_a_specific_subject(self):
        topics = [
            "History of Bali",
            "How Kubernetes taints affect scheduling",
            "How CRISPR edits DNA",
            "Why Roman aqueducts used gradients",
        ]
        for topic in topics:
            with self.subTest(topic=topic):
                queries = {
                    "topic": topic,
                    "queries": [f"What are the main mechanisms and evidence for {topic}?"],
                    "required_concepts": ["mechanism", "evidence"],
                }
                result = retrieve_sources_evidence_first(
                    queries, FakeResearchBackend(), ComparativeModel()
                )
                self.assertEqual(len(result["sources"]), 1)
                self.assertEqual(result["sources"][0]["url"], "https://example.test/primary")
                self.assertEqual(
                    result["retrieval_strategy"],
                    "evidence-first-comparative-selection",
                )

    def test_invalid_model_selection_falls_back_deterministically(self):
        queries = {
            "topic": "Arbitrary topic",
            "queries": ["Explain the mechanism and evidence"],
            "required_concepts": ["mechanism"],
        }
        result = retrieve_sources_evidence_first(
            queries, FakeResearchBackend(), InvalidSelectionModel()
        )
        self.assertEqual(
            result["sources"][0]["selection_method"],
            "deterministic-fallback",
        )
        self.assertEqual(result["sources"][0]["url"], "https://example.test/primary")

    def test_retrieval_fails_only_when_no_usable_document_exists(self):
        class EmptyBackend(FakeResearchBackend):
            def fetch(self, url):
                return "too short"

        queries = {
            "topic": "Any topic",
            "queries": ["Any research question"],
            "required_concepts": ["evidence"],
        }
        with self.assertRaisesRegex(ValueError, "no usable source document"):
            retrieve_sources_evidence_first(
                queries, EmptyBackend(), ComparativeModel()
            )


if __name__ == "__main__":
    unittest.main()
