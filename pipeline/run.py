from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.content_pipeline import ContentPipeline, GitHubModelsClient
from pipeline.context import RunContext
from pipeline.orchestrator import Orchestrator
from pipeline.research import ResilientWikipediaResearchBackend


def stage_content(context: RunContext) -> None:
    pipeline = ContentPipeline(GitHubModelsClient(), ResilientWikipediaResearchBackend())
    artifacts = pipeline.run(context.topic)
    for name, payload in artifacts.items():
        (context.run_dir / f"{name}.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
    (context.run_dir / "script.json").write_text(
        json.dumps(artifacts["07_script"], indent=2) + "\n", encoding="utf-8"
    )


def stage_render_manifest(context: RunContext) -> None:
    validation = json.loads((context.run_dir / "08_validation.json").read_text(encoding="utf-8"))
    payload = {
        "run_id": context.run_id,
        "mode": "content-ready",
        "script": "script.json",
        "sources": validation["source_urls"],
        "message": "Rendering remains deferred until its own red-green cycle.",
    }
    (context.run_dir / "render.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def build_orchestrator() -> Orchestrator:
    return Orchestrator(
        [
            (1, "research-and-script", stage_content),
            (2, "render-manifest", stage_render_manifest),
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the faceless pipeline in GitHub Actions")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--from-stage", type=int, default=1)
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    context = RunContext.create(args.runs_dir, args.topic, args.run_id)
    print(f"RUN_ID={context.run_id}")
    build_orchestrator().run(context, from_stage=args.from_stage)
    print(f"RUN_DIR={context.run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
