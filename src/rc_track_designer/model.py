"""Framework-unabhängiges Geometriemodell (alle Maße in Metern)."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, hypot, radians, sin
from uuid import uuid4


MINIMUM_CURVE_INNER_RADIUS = 0.0


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Pose:
    point: Point
    heading_deg: float


@dataclass(frozen=True)
class ConnectorRef:
    element_id: str
    endpoint: str

    def __post_init__(self) -> None:
        if (self.endpoint not in {"start", "end"}
                and not self.endpoint.startswith("magnet:")):
            raise ValueError("Unknown connector endpoint")


@dataclass(frozen=True)
class TrackConnection:
    first: ConnectorRef
    second: ConnectorRef

    def __post_init__(self) -> None:
        if self.first == self.second:
            raise ValueError("A connector cannot connect to itself")

    def contains(self, connector: ConnectorRef) -> bool:
        return connector in (self.first, self.second)

    def to_dict(self) -> dict:
        return {"first": vars(self.first), "second": vars(self.second)}

    @classmethod
    def from_dict(cls, data: dict) -> "TrackConnection":
        return cls(ConnectorRef(**data["first"]), ConnectorRef(**data["second"]))


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
    rotation_reference_deg: float | None = None
    element_type: str = "track"
    magnet_points: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in {"straight", "left", "right"}:
            raise ValueError(f"Unbekannter Elementtyp: {self.kind}")
        if self.element_type not in {"track", "boundary"}:
            raise ValueError(f"Unbekannte Elementkategorie: {self.element_type}")
        if self.width <= 0 or self.length <= 0 or self.radius <= 0:
            raise ValueError("Breite, Länge und Radius müssen positiv sein")
        if not 0 < self.angle_deg <= 360:
            raise ValueError("Kurvenwinkel muss zwischen 0 und 360 Grad liegen")
        self.heading_deg %= 360
        if self.rotation_reference_deg is None:
            self.rotation_reference_deg = self.heading_deg
        else:
            self.rotation_reference_deg %= 360
        if self.magnet_points and (self.element_type != "boundary" or self.kind != "straight"):
            raise ValueError("Additional magnet points require a straight boundary")
        if any(not 0.0 < float(position) < 1.0
               for position in self.magnet_points.values()):
            raise ValueError("Magnet point positions must lie inside the element")

    @property
    def signed_angle_deg(self) -> float:
        return self.angle_deg if self.kind == "left" else -self.angle_deg

    @property
    def minimum_centerline_radius(self) -> float:
        """Smallest radius that leaves a valid inner road edge."""
        return self.width / 2 + MINIMUM_CURVE_INNER_RADIUS

    @property
    def has_valid_road_geometry(self) -> bool:
        return (self.kind == "straight"
                or self.radius + 1e-9 >= self.minimum_centerline_radius)

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

    def pose_at(self, endpoint: str) -> Pose:
        if endpoint == "start": return self.start_pose
        if endpoint == "end": return self.end_pose
        if endpoint.startswith("magnet:"):
            point_id = endpoint.split(":", 1)[1]
            if point_id not in self.magnet_points:
                raise ValueError("Unknown magnet point")
            distance = self.length * self.magnet_points[point_id]
            angle = radians(self.heading_deg)
            return Pose(Point(self.start.x + distance * cos(angle),
                              self.start.y + distance * sin(angle)),
                        self.heading_deg % 360)
        raise ValueError("Endpoint must be 'start' or 'end'")

    @property
    def connector_names(self) -> tuple[str, ...]:
        return ("start", "end", *(f"magnet:{point_id}"
                                  for point_id in self.magnet_points))

    def align_endpoint(self, endpoint: str, target: Pose) -> None:
        if endpoint == "start":
            self.start = target.point
            self.heading_deg = target.heading_deg % 360
            self.rotation_reference_deg = self.heading_deg
            return
        if endpoint != "end":
            raise ValueError("Endpoint must be 'start' or 'end'")
        self.heading_deg = ((target.heading_deg - self.signed_angle_deg) if self.kind != "straight" else target.heading_deg) % 360
        current = self.end_pose.point
        self.start = Point(self.start.x + target.point.x - current.x, self.start.y + target.point.y - current.y)
        self.rotation_reference_deg = self.heading_deg

    @property
    def centerline_midpoint(self) -> Point:
        if self.kind == "straight":
            end = self.end_pose.point
            return Point((self.start.x + end.x) / 2, (self.start.y + end.y) / 2)
        heading = radians(self.heading_deg)
        turn = 1 if self.kind == "left" else -1
        center = Point(
            self.start.x - turn * self.radius * sin(heading),
            self.start.y + turn * self.radius * cos(heading),
        )
        radial = heading - turn * radians(90)
        middle_radial = radial + radians(self.signed_angle_deg / 2)
        return Point(center.x + self.radius * cos(middle_radial),
                     center.y + self.radius * sin(middle_radial))

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
        pivot = self.centerline_midpoint
        angle = radians(delta_deg)
        dx, dy = self.start.x - pivot.x, self.start.y - pivot.y
        self.start = Point(
            pivot.x + dx * cos(angle) - dy * sin(angle),
            pivot.y + dx * sin(angle) + dy * cos(angle),
        )
        self.heading_deg = (self.heading_deg + delta_deg) % 360

    def to_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind,
            "start": {"x": self.start.x, "y": self.start.y},
            "heading_deg": self.heading_deg, "width": self.width,
            "length": self.length, "radius": self.radius, "angle_deg": self.angle_deg,
            "rotation_reference_deg": self.rotation_reference_deg,
            "element_type": self.element_type,
            "magnet_points": self.magnet_points,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TrackElement":
        return cls(
            id=str(data["id"]), kind=str(data["kind"]),
            start=Point(float(data["start"]["x"]), float(data["start"]["y"])),
            heading_deg=float(data["heading_deg"]), width=float(data["width"]),
            length=float(data.get("length", 5.0)), radius=float(data.get("radius", 5.0)),
            angle_deg=float(data.get("angle_deg", 45.0)),
            rotation_reference_deg=(float(data["rotation_reference_deg"])
                                    if data.get("rotation_reference_deg") is not None else None),
            element_type=str(data.get("element_type", "track")),
            magnet_points={str(key): float(value)
                           for key, value in data.get("magnet_points", {}).items()},
        )


@dataclass
class TrackProject:
    hall_length: float = 30.0
    hall_width: float = 20.0
    elements: list[TrackElement] = field(default_factory=list)
    connections: list[TrackConnection] = field(default_factory=list)
    guides_x: list[float] = field(default_factory=list)
    guides_y: list[float] = field(default_factory=list)
    editor_mode: str = "normal"

    def __post_init__(self) -> None:
        if self.editor_mode not in {"normal", "indoor"}:
            raise ValueError("Unknown editor mode")
        if self.hall_length <= 0 or self.hall_width <= 0:
            raise ValueError("Streckenbereichsmaße müssen positiv sein")
        if any(not 0 <= value <= self.hall_length for value in self.guides_x):
            raise ValueError("Vertical guide lies outside the track area")
        if any(not 0 <= value <= self.hall_width for value in self.guides_y):
            raise ValueError("Horizontal guide lies outside the track area")
        self.validate_connections()

    def element_by_id(self, element_id: str) -> TrackElement | None:
        return next((item for item in self.elements if item.id == element_id), None)

    def connector_pose(self, connector: ConnectorRef) -> Pose:
        element = self.element_by_id(connector.element_id)
        if element is None: raise ValueError("Unknown element")
        return element.pose_at(connector.endpoint)

    def connection_for(self, connector: ConnectorRef) -> TrackConnection | None:
        return next((item for item in self.connections if item.contains(connector)), None)

    def connections_for(self, connector: ConnectorRef) -> list[TrackConnection]:
        return [item for item in self.connections if item.contains(connector)]

    def is_multi_connection_connector(self, connector: ConnectorRef) -> bool:
        element = self.element_by_id(connector.element_id)
        return bool(
            element is not None
            and element.element_type == "boundary"
            and connector.endpoint in element.connector_names
        )

    def is_free(self, connector: ConnectorRef) -> bool:
        return self.element_by_id(connector.element_id) is not None and self.connection_for(connector) is None

    def can_accept_connection(self, connector: ConnectorRef) -> bool:
        return (self.element_by_id(connector.element_id) is not None
                and (self.is_free(connector)
                     or self.is_multi_connection_connector(connector)))

    @staticmethod
    def connection_target_pose(moving: ConnectorRef, stationary: ConnectorRef,
                               stationary_pose: Pose) -> Pose:
        """Pose a moving endpoint needs for an undirected tangent connection."""
        heading = stationary_pose.heading_deg
        if moving.endpoint == stationary.endpoint:
            heading += 180
        return Pose(stationary_pose.point, heading % 360)

    def connector_alignment_pose(self, moving: ConnectorRef,
                                 stationary: ConnectorRef) -> Pose:
        return self.connection_target_pose(
            moving, stationary, self.connector_pose(stationary)
        )

    def connector_alignment_error(self, first: ConnectorRef,
                                  second: ConnectorRef) -> tuple[float, float]:
        first_pose = self.connector_pose(first)
        target = self.connector_alignment_pose(first, second)
        distance = hypot(first_pose.point.x - target.point.x,
                         first_pose.point.y - target.point.y)
        angle = abs((first_pose.heading_deg - target.heading_deg + 180) % 360 - 180)
        return distance, angle

    def connect(self, first: ConnectorRef, second: ConnectorRef) -> TrackConnection:
        if first.element_id == second.element_id: raise ValueError("Self-connections are not valid")
        first_element = self.element_by_id(first.element_id)
        second_element = self.element_by_id(second.element_id)
        if (first_element is None or second_element is None
                or first_element.element_type != second_element.element_type):
            raise ValueError("Only elements of the same category can be connected")
        if (not self.can_accept_connection(first)
                or not self.can_accept_connection(second)):
            raise ValueError("Both connectors must accept a connection")
        if any(item.contains(first) and item.contains(second)
               for item in self.connections):
            raise ValueError("The connection already exists")
        distance, angle = self.connector_alignment_error(first, second)
        if (first_element.element_type == "track"
                and (distance > 1e-6 or angle > 1e-6)):
            raise ValueError("Connected endpoints must share position and tangent line")
        if distance > 1e-6:
            raise ValueError("Connected boundary endpoints must share a position")
        connection = TrackConnection(first, second)
        self.connections.append(connection)
        return connection

    def disconnect_element(self, element_id: str) -> list[TrackConnection]:
        removed = [item for item in self.connections if item.first.element_id == element_id or item.second.element_id == element_id]
        self.connections = [item for item in self.connections if item not in removed]
        return removed

    def disconnect(self, connector: ConnectorRef) -> TrackConnection | None:
        connection = self.connection_for(connector)
        if connection is not None: self.connections.remove(connection)
        return connection

    def disconnect_all(self, connector: ConnectorRef) -> list[TrackConnection]:
        removed = self.connections_for(connector)
        self.connections = [item for item in self.connections if item not in removed]
        return removed

    def remove_element(self, element: TrackElement) -> None:
        self.disconnect_element(element.id)
        self.elements.remove(element)

    def validate_connections(self) -> None:
        occupied: set[ConnectorRef] = set()
        ids = {item.id for item in self.elements}
        for connection in self.connections:
            if connection.first.element_id == connection.second.element_id:
                raise ValueError("Self-connections are not valid")
            for connector in (connection.first, connection.second):
                if connector.element_id not in ids: raise ValueError("Connection references an unknown element")
                if (connector in occupied
                        and not self.is_multi_connection_connector(connector)):
                    raise ValueError("A connector cannot have multiple connections")
                occupied.add(connector)
            first_element = self.element_by_id(connection.first.element_id)
            second_element = self.element_by_id(connection.second.element_id)
            if first_element.element_type != second_element.element_type:
                raise ValueError("Connected elements must have the same category")
            distance, angle = self.connector_alignment_error(
                connection.first, connection.second
            )
            if distance > 1e-6:
                raise ValueError("Connected endpoints do not share a position")
            if first_element.element_type == "track" and angle > 1e-6:
                raise ValueError("Connected endpoints do not share a tangent line")

    def element_fits_hall(self, element: TrackElement) -> bool:
        """Return whether the complete road surface lies inside the track area."""
        margin = element.width / 2
        tolerance = 1e-9
        return all(
            margin - tolerance <= point.x <= self.hall_length - margin + tolerance
            and margin - tolerance <= point.y <= self.hall_width - margin + tolerance
            for point in element.centerline_points(maximum_step_deg=1.0)
        )

    def all_elements_fit_hall(self) -> bool:
        return all(self.element_fits_hall(element) for element in self.elements)

    def clamp_translation(self, element: TrackElement, dx: float, dy: float) -> tuple[float, float]:
        """Clamp a translation so the complete road remains inside the track area."""
        points = element.centerline_points(maximum_step_deg=1.0)
        margin = element.width / 2
        minimum_x = min(point.x for point in points)
        maximum_x = max(point.x for point in points)
        minimum_y = min(point.y for point in points)
        maximum_y = max(point.y for point in points)
        dx = min(max(dx, margin - minimum_x), self.hall_length - margin - maximum_x)
        dy = min(max(dy, margin - minimum_y), self.hall_width - margin - maximum_y)
        return dx, dy

    def clamp_group_translation(self, elements: list[TrackElement], dx: float, dy: float) -> tuple[float, float]:
        if not elements: return 0.0, 0.0
        minimum_dx, maximum_dx = float("-inf"), float("inf")
        minimum_dy, maximum_dy = float("-inf"), float("inf")
        for element in elements:
            points = element.centerline_points(maximum_step_deg=1.0)
            margin = element.width / 2
            minimum_dx = max(minimum_dx, margin - min(point.x for point in points))
            maximum_dx = min(maximum_dx, self.hall_length - margin - max(point.x for point in points))
            minimum_dy = max(minimum_dy, margin - min(point.y for point in points))
            maximum_dy = min(maximum_dy, self.hall_width - margin - max(point.y for point in points))
        return min(max(dx, minimum_dx), maximum_dx), min(max(dy, minimum_dy), maximum_dy)
