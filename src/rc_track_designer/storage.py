"""Versionierte JSON-Projektspeicherung."""

from __future__ import annotations

import json
from pathlib import Path

from .model import TrackConnection, TrackElement, TrackProject

FORMAT_VERSION = 2


def save_project(project: TrackProject, path: str | Path) -> None:
    data = {
        "format": "rc-track-designer", "format_version": FORMAT_VERSION,
        "app_version": "0.2.0",
        "hall": {"length": project.hall_length, "width": project.hall_width},
        "elements": [element.to_dict() for element in project.elements],
        "connections": [connection.to_dict() for connection in project.connections],
        "guides": {"x": project.guides_x, "y": project.guides_y},
    }
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_project(path: str | Path) -> TrackProject:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    version = data.get("format_version")
    if data.get("format") != "rc-track-designer" or version not in {1, FORMAT_VERSION}:
        raise ValueError("Nicht unterstütztes Projektformat")
    hall = data["hall"]
    guides = data.get("guides", {})
    return TrackProject(
        float(hall["length"]), float(hall["width"]),
        [TrackElement.from_dict(item) for item in data.get("elements", [])],
        [TrackConnection.from_dict(item) for item in data.get("connections", [])] if version >= 2 else [],
        [float(value) for value in guides.get("x", [])],
        [float(value) for value in guides.get("y", [])],
    )
