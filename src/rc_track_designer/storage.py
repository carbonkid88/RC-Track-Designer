"""Versionierte JSON-Projektspeicherung."""

from __future__ import annotations

import json
from pathlib import Path

from .model import ConnectorRef, TrackConnection, TrackElement, TrackProject

FORMAT_VERSION = 4


def _load_valid_connections(elements: list[TrackElement], raw_connections: list[dict]) -> list[TrackConnection]:
    """Keep usable saved links without making the entire project unloadable.

    Some early editor versions could leave a stale connection behind after a
    geometry edit. Elements are more valuable than that derived link, so an
    invalid link is released while every element remains untouched.
    """
    project = TrackProject(elements=elements)
    occupied: set[ConnectorRef] = set()
    valid: list[TrackConnection] = []
    for raw in raw_connections:
        try:
            connection = TrackConnection.from_dict(raw)
            first, second = connection.first, connection.second
            first_element = project.element_by_id(first.element_id)
            second_element = project.element_by_id(second.element_id)
            if (first_element is None or second_element is None
                    or first.element_id == second.element_id
                    or first_element.element_type != second_element.element_type
                    or first in occupied or second in occupied):
                continue
            distance, angle = project.connector_alignment_error(first, second)
            if distance > 1e-6:
                continue
            if first_element.element_type == "track" and angle > 1e-6:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        valid.append(connection)
        occupied.update((first, second))
    return valid


def save_project(project: TrackProject, path: str | Path) -> None:
    data = {
        "format": "rc-track-designer", "format_version": FORMAT_VERSION,
        "app_version": "0.4.0",
        "editor_mode": project.editor_mode,
        "hall": {"length": project.hall_length, "width": project.hall_width},
        "elements": [element.to_dict() for element in project.elements],
        "connections": [connection.to_dict() for connection in project.connections],
        "guides": {"x": project.guides_x, "y": project.guides_y},
    }
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_project(path: str | Path) -> TrackProject:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    version = data.get("format_version")
    if data.get("format") != "rc-track-designer" or version not in {1, 2, 3, FORMAT_VERSION}:
        raise ValueError("Nicht unterstütztes Projektformat")
    hall = data["hall"]
    guides = data.get("guides", {})
    elements = [TrackElement.from_dict(item) for item in data.get("elements", [])]
    connections = (_load_valid_connections(elements, data.get("connections", []))
                   if version >= 2 else [])
    return TrackProject(
        float(hall["length"]), float(hall["width"]),
        elements,
        connections,
        [float(value) for value in guides.get("x", [])],
        [float(value) for value in guides.get("y", [])],
        str(data.get("editor_mode", "normal")),
    )
