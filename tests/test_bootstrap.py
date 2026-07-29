import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from pipeline.context import RunContext, slugify
from pipeline.orchestrator import Orchestrator, StageFailure


class RunContextTests(unittest.TestCase):
    def test_slugify_is_filesystem_safe(self):
        self.assertEqual(slugify("Why Airplane Windows Are Round!?"), "why-airplane-windows-are-round")

    def test_run_context_creates_expected_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = RunContext.create(Path(tmp), "Test Topic", run_id="20260729-test-topic")
            self.assertTrue(ctx.run_dir.is_dir())
            self.assertEqual(ctx.topic_file.read_text(), "Test Topic")
            self.assertEqual(ctx.status_file.read_text(), "created\n")


class OrchestratorTests(unittest.TestCase):
    def test_stages_run_in_order_and_write_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = RunContext.create(Path(tmp), "Topic", run_id="run-1")
            seen = []

            def stage(name):
                def execute(context):
                    seen.append(name)
                    (context.run_dir / f"{name}.txt").write_text(name)
                return execute

            orchestrator = Orchestrator([
                (1, "script", stage("script")),
                (2, "render", stage("render")),
            ])
            orchestrator.run(ctx)

            self.assertEqual(seen, ["script", "render"])
            manifest = json.loads(ctx.manifest_file.read_text())
            self.assertEqual([item["status"] for item in manifest["stages"]], ["completed", "completed"])

    def test_from_stage_skips_earlier_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = RunContext.create(Path(tmp), "Topic", run_id="run-2")
            seen = []
            orchestrator = Orchestrator([
                (1, "one", lambda context: seen.append("one")),
                (2, "two", lambda context: seen.append("two")),
            ])
            orchestrator.run(ctx, from_stage=2)
            self.assertEqual(seen, ["two"])

    def test_failure_is_recorded_and_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = RunContext.create(Path(tmp), "Topic", run_id="run-3")

            def fail(_context):
                raise RuntimeError("boom")

            orchestrator = Orchestrator([(1, "explode", fail)])
            with self.assertRaises(StageFailure):
                orchestrator.run(ctx)

            manifest = json.loads(ctx.manifest_file.read_text())
            self.assertEqual(manifest["stages"][0]["status"], "failed")
            self.assertIn("boom", manifest["stages"][0]["error"])
            self.assertTrue(ctx.run_dir.exists())


class PhoneContractTests(unittest.TestCase):
    def test_phone_script_only_controls_github_actions(self):
        script = Path("phone/generate.sh").read_text()
        self.assertIn("gh workflow run", script)
        self.assertIn("gh run watch", script)
        self.assertIn("gh run download", script)
        for forbidden in ("python ", "python3 ", "ffmpeg", "pip install"):
            self.assertNotIn(forbidden, script)


if __name__ == "__main__":
    unittest.main()
