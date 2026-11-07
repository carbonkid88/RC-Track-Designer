"""Versionierte JSON-Projektspeicherung."""

from __future__ import annotations

import json
from pathlib import Path

from .model import TrackElement, TrackProject

FORMAT_VERSION = 1


def save_project(project: TrackProject, path: str | Path) -> None:
    data = {
        "format": "rc-track-designer", "format_version": FORMAT_VERSION,
        "app_version": "0.1.1",
        "hall": {"length": project.hall_length, "width": project.hall_width},
        "elements": [element.to_dict() for element in project.elements],
    }
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_project(path: str | Path) -> TrackProject:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != "rc-track-designer" or data.get("format_version") != FORMAT_VERSION:
        raise ValueError("Nicht unterstütztes Projektformat")
    hall = data["hall"]
    return TrackProject(
        float(hall["length"]), float(hall["width"]),
        [TrackElement.from_dict(item) for item in data.get("elements", [])],
    )
