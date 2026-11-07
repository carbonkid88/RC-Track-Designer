"""Framework-unabhängiges Geometriemodell (alle Maße in Metern)."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, radians, sin
from uuid import uuid4


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Pose:
    point: Point
    heading_deg: float


@dataclass
class TrackElement:
    kind: str
    start: Point
    heading_deg: float = 0.0
    width: float = 2.0
    length: float = 5.0
    radius: float = 5.0
    angle_deg: float = 45.0
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if self.kind not in {"straight", "left", "right"}:
            raise ValueError(f"Unbekannter Elementtyp: {self.kind}")
        if self.width <= 0 or self.length <= 0 or self.radius <= 0:
            raise ValueError("Breite, Länge und Radius müssen positiv sein")
        if not 0 < self.angle_deg <= 360:
            raise ValueError("Kurvenwinkel muss zwischen 0 und 360 Grad liegen")

    @property
    def signed_angle_deg(self) -> float:
        return self.angle_deg if self.kind == "left" else -self.angle_deg

    @property
    def end_pose(self) -> Pose:
        a = radians(self.heading_deg)
        if self.kind == "straight":
            p = Point(self.start.x + self.length * cos(a), self.start.y + self.length * sin(a))
            return Pose(p, self.heading_deg % 360)
        delta = radians(self.signed_angle_deg)
        turn = 1 if self.kind == "left" else -1
        # Mittelpunkt liegt links bzw. rechts von der Anfangstangente.
        cx = self.start.x - turn * self.radius * sin(a)
        cy = self.start.y + turn * self.radius * cos(a)
        radial = a - turn * radians(90)
        end_radial = radial + delta
        p = Point(cx + self.radius * cos(end_radial), cy + self.radius * sin(end_radial))
        return Pose(p, (self.heading_deg + self.signed_angle_deg) % 360)

    @property
    def start_pose(self) -> Pose:
        return Pose(self.start, self.heading_deg % 360)

    def centerline_points(self, maximum_step_deg: float = 5.0) -> list[Point]:
        if self.kind == "straight":
            return [self.start, self.end_pose.point]
        count = max(2, int(self.angle_deg / maximum_step_deg) + 1)
        result: list[Point] = []
        for i in range(count + 1):
            partial = self.signed_angle_deg * i / count
            temp = TrackElement(
                self.kind, self.start, self.heading_deg, self.width,
                self.length, self.radius, abs(partial) if partial else 0.000001, self.id,
            )
            result.append(self.start if i == 0 else temp.end_pose.point)
        return result

    def moved(self, dx: float, dy: float) -> None:
        self.start = Point(self.start.x + dx, self.start.y + dy)

    def rotate(self, delta_deg: float) -> None:
        self.heading_deg = (self.heading_deg + delta_deg) % 360

    def to_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind,
            "start": {"x": self.start.x, "y": self.start.y},
            "heading_deg": self.heading_deg, "width": self.width,
            "length": self.length, "radius": self.radius, "angle_deg": self.angle_deg,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TrackElement":
        return cls(
            id=str(data["id"]), kind=str(data["kind"]),
            start=Point(float(data["start"]["x"]), float(data["start"]["y"])),
            heading_deg=float(data["heading_deg"]), width=float(data["width"]),
            length=float(data.get("length", 5.0)), radius=float(data.get("radius", 5.0)),
            angle_deg=float(data.get("angle_deg", 45.0)),
        )


@dataclass
class TrackProject:
    hall_length: float = 30.0
    hall_width: float = 20.0
    elements: list[TrackElement] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.hall_length <= 0 or self.hall_width <= 0:
            raise ValueError("Hallenmaße müssen positiv sein")
