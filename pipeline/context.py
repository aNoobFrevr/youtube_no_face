from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "untitled"


@dataclass(frozen=True)
class RunContext:
    root: Path
    run_id: str
    topic: str

    @property
    def run_dir(self) -> Path:
        return self.root / self.run_id

    @property
    def topic_file(self) -> Path:
        return self.run_dir / "topic.txt"

    @property
    def status_file(self) -> Path:
        return self.run_dir / "status.txt"

    @property
    def manifest_file(self) -> Path:
        return self.run_dir / "manifest.json"

    @classmethod
    def create(cls, root: Path, topic: str, run_id: str | None = None) -> "RunContext":
        resolved_id = run_id or f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{slugify(topic)}"
        context = cls(root=root, run_id=resolved_id, topic=topic)
        context.run_dir.mkdir(parents=True, exist_ok=True)
        context.topic_file.write_text(topic, encoding="utf-8")
        context.status_file.write_text("created\n", encoding="utf-8")
        return context
