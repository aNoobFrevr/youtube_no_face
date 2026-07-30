from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.content_pipeline import ContentPipeline, GitHubModelsClient
from pipeline.context import RunContext
from pipeline.research import ResilientWikipediaResearchBackend


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the eight-stage research pipeline")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"))
    return parser.parse_args()


def persist_artifacts(context: RunContext, artifacts: dict[str, dict]) -> None:
    for name, payload in artifacts.items():
        (context.run_dir / f"{name}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    manifest = {
        "run_id": context.run_id,
        "topic": context.topic,
        "mode": "eight-stage-research-pipeline",
        "artifacts": [f"{name}.json" for name in artifacts],
        "validation": artifacts["08_validation"],
    }
    context.manifest_file.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    context.status_file.write_text("completed\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    context = RunContext.create(args.runs_dir, args.topic, args.run_id)
    print(f"RUN_ID={context.run_id}")

    try:
        pipeline = ContentPipeline(
            model=GitHubModelsClient(),
            research=ResilientWikipediaResearchBackend(),
        )
        artifacts = pipeline.run(context.topic)
        persist_artifacts(context, artifacts)
    except Exception:
        context.status_file.write_text("failed\n", encoding="utf-8")
        raise

    print(f"RUN_DIR={context.run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
