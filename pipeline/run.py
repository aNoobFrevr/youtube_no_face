from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.context import RunContext
from pipeline.orchestrator import Orchestrator


def stage_script(context: RunContext) -> None:
    payload = {
        "topic": context.topic,
        "hook": f"Here is what makes {context.topic} interesting.",
        "segments": [],
        "cta": "Follow for the full build.",
    }
    (context.run_dir / "script.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def stage_render_manifest(context: RunContext) -> None:
    payload = {
        "run_id": context.run_id,
        "mode": "bootstrap-smoke-test",
        "message": "Rendering is intentionally deferred until its own red-green cycle.",
    }
    (context.run_dir / "render.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def build_orchestrator() -> Orchestrator:
    return Orchestrator(
        [
            (1, "script", stage_script),
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
