from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Iterable

from pipeline.context import RunContext

StageCallable = Callable[[RunContext], None]


@dataclass
class StageFailure(RuntimeError):
    stage_number: int
    stage_name: str
    cause: Exception

    def __str__(self) -> str:
        return f"stage {self.stage_number} ({self.stage_name}) failed: {self.cause}"


class Orchestrator:
    def __init__(self, stages: Iterable[tuple[int, str, StageCallable]]):
        self.stages = list(stages)

    def run(self, context: RunContext, from_stage: int = 1) -> None:
        manifest = {
            "run_id": context.run_id,
            "topic": context.topic,
            "stages": [],
        }
        context.status_file.write_text("running\n", encoding="utf-8")

        for number, name, execute in self.stages:
            if number < from_stage:
                manifest["stages"].append(
                    {"number": number, "name": name, "status": "skipped"}
                )
                self._write_manifest(context, manifest)
                continue

            record = {"number": number, "name": name, "status": "running"}
            manifest["stages"].append(record)
            self._write_manifest(context, manifest)

            try:
                execute(context)
            except Exception as exc:
                record["status"] = "failed"
                record["error"] = str(exc)
                context.status_file.write_text("failed\n", encoding="utf-8")
                self._write_manifest(context, manifest)
                raise StageFailure(number, name, exc) from exc

            record["status"] = "completed"
            self._write_manifest(context, manifest)

        context.status_file.write_text("completed\n", encoding="utf-8")

    @staticmethod
    def _write_manifest(context: RunContext, manifest: dict) -> None:
        context.manifest_file.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
