"""Geometry and vector rendering for Indoor restricted areas."""

from __future__ import annotations

from collections.abc import Callable
from math import atan2, cos, degrees, hypot, radians, sin

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QBrush, QPainter, QPainterPath, QPen, QPolygonF

from .model import PlanningObject, Point

PointMapper = Callable[[Point], QPointF]


def local_to_world(item: PlanningObject, point: Point) -> Point:
    angle = radians(item.heading_deg)
    return Point(item.center.x + point.x * cos(angle) - point.y * sin(angle),
                 item.center.y + point.x * sin(angle) + point.y * cos(angle))


def world_to_local(item: PlanningObject, point: Point) -> Point:
    angle = radians(item.heading_deg)
    dx, dy = point.x - item.center.x, point.y - item.center.y
    return Point(dx * cos(angle) + dy * sin(angle),
                 -dx * sin(angle) + dy * cos(angle))


def polygon_world_points(item: PlanningObject) -> list[Point]:
    return [local_to_world(item, point) for point in item.points]


def orientation(a: Point, b: Point, c: Point) -> float:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    ab_c, ab_d = orientation(a, b, c), orientation(a, b, d)
    cd_a, cd_b = orientation(c, d, a), orientation(c, d, b)
    if ab_c * ab_d < -1e-10 and cd_a * cd_b < -1e-10:
        return True
    def on_segment(first: Point, point: Point, last: Point) -> bool:
        return (min(first.x, last.x) - 1e-10 <= point.x <= max(first.x, last.x) + 1e-10
                and min(first.y, last.y) - 1e-10 <= point.y <= max(first.y, last.y) + 1e-10)
    return ((abs(ab_c) <= 1e-10 and on_segment(a, c, b))
            or (abs(ab_d) <= 1e-10 and on_segment(a, d, b))
            or (abs(cd_a) <= 1e-10 and on_segment(c, a, d))
            or (abs(cd_b) <= 1e-10 and on_segment(c, b, d)))


def valid_polygon(points: list[Point]) -> bool:
    if len(points) < 3 or len({(round(p.x, 9), round(p.y, 9)) for p in points}) < 3:
        return False
    area = sum(points[i].x * points[(i + 1) % len(points)].y
               - points[(i + 1) % len(points)].x * points[i].y
               for i in range(len(points)))
    if abs(area) < 1e-8:
        return False
    count = len(points)
    for i in range(count):
        for j in range(i + 1, count):
            if j in {i, (i + 1) % count} or i == (j + 1) % count:
                continue
            if _segments_intersect(points[i], points[(i + 1) % count],
                                   points[j], points[(j + 1) % count]):
                return False
    return True


def polygon_from_world(points: list[Point]) -> PlanningObject:
    center = Point(sum(point.x for point in points) / len(points),
                   sum(point.y for point in points) / len(points))
    local = [Point(point.x - center.x, point.y - center.y) for point in points]
    return PlanningObject("restricted_polygon", center, points=local)


def restricted_path(item: PlanningObject, map_point: PointMapper) -> QPainterPath:
    path = QPainterPath()
    if item.kind == "restricted_circle":
        center = map_point(item.center)
        edge = map_point(Point(item.center.x + item.length / 2, item.center.y))
        radius = hypot(edge.x() - center.x(), edge.y() - center.y())
        path.addEllipse(center, radius, radius)
    else:
        points = polygon_world_points(item) if item.kind == "restricted_polygon" else list(item.corners())
        path.addPolygon(QPolygonF([map_point(point) for point in points]))
        path.closeSubpath()
    return path


def restricted_hit_test(item: PlanningObject, screen: QPointF,
                        map_point: PointMapper, tolerance: float = 5) -> bool:
    path = restricted_path(item, map_point)
    if path.contains(screen):
        return True
    outline = QPainterPath()
    pen = QPen(Qt.GlobalColor.black, tolerance * 2)
    outline = QPainterPathStrokerCompat.stroke(path, pen.widthF())
    return outline.contains(screen)


class QPainterPathStrokerCompat:
    @staticmethod
    def stroke(path: QPainterPath, width: float) -> QPainterPath:
        from PySide6.QtGui import QPainterPathStroker
        stroker = QPainterPathStroker()
        stroker.setWidth(width)
        return stroker.createStroke(path)


def circle_handle(item: PlanningObject) -> Point:
    return Point(item.center.x + item.length / 2, item.center.y)


def draw_restricted_area(painter: QPainter, item: PlanningObject,
                         map_point: PointMapper, units_per_metre: float,
                         *, selected: bool = False, grayscale: bool = False) -> None:
    path = restricted_path(item, map_point)
    fill = QColor("#777777" if grayscale else "#8b9299")
    outline = QColor("#303030" if grayscale else "#555d65")
    brush = QBrush(fill, Qt.BrushStyle.BDiagPattern)
    painter.setBrush(brush)
    painter.setPen(QPen(outline, max(1.0, units_per_metre * 0.018)))
    painter.drawPath(path)
    if selected:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#ffb020"), 3))
        painter.drawPath(path)


def nearest_polygon_edge(item: PlanningObject, point: Point) -> tuple[int, Point, float] | None:
    points = polygon_world_points(item)
    best = None
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        dx, dy = end.x - start.x, end.y - start.y
        length2 = dx * dx + dy * dy
        fraction = 0 if length2 == 0 else max(0, min(1, ((point.x - start.x) * dx + (point.y - start.y) * dy) / length2))
        candidate = Point(start.x + fraction * dx, start.y + fraction * dy)
        distance = hypot(candidate.x - point.x, candidate.y - point.y)
        if best is None or distance < best[2]:
            best = (index, candidate, distance)
    return best


def nearest_restricted_contour(item: PlanningObject, point: Point) -> tuple[Point, float]:
    """Return the closest metric point on a restricted-area outline."""
    if item.kind == "restricted_circle":
        dx, dy = point.x - item.center.x, point.y - item.center.y
        distance_to_center = hypot(dx, dy)
        radius = item.length / 2
        if distance_to_center <= 1e-12:
            candidate = Point(item.center.x + radius, item.center.y)
        else:
            candidate = Point(item.center.x + dx * radius / distance_to_center,
                              item.center.y + dy * radius / distance_to_center)
        return candidate, abs(distance_to_center - radius)
    if item.kind == "restricted_polygon":
        edge = nearest_polygon_edge(item, point)
        assert edge is not None
        return edge[1], edge[2]
    points = list(item.corners())
    best: tuple[Point, float] | None = None
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        dx, dy = end.x - start.x, end.y - start.y
        length2 = dx * dx + dy * dy
        fraction = max(0, min(1, ((point.x - start.x) * dx + (point.y - start.y) * dy) / length2))
        candidate = Point(start.x + fraction * dx, start.y + fraction * dy)
        distance = hypot(candidate.x - point.x, candidate.y - point.y)
        if best is None or distance < best[1]:
            best = candidate, distance
    assert best is not None
    return best


def restricted_contour_tangent(item: PlanningObject, point: Point) -> float:
    """Heading in degrees of the contour nearest ``point``."""
    if item.kind == "restricted_circle":
        radial = degrees(atan2(point.y - item.center.y,
                               point.x - item.center.x))
        return (radial + 90) % 360
    points = (polygon_world_points(item) if item.kind == "restricted_polygon"
              else list(item.corners()))
    best = None
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        dx, dy = end.x - start.x, end.y - start.y
        length2 = dx * dx + dy * dy
        fraction = max(0, min(1, ((point.x - start.x) * dx
                                  + (point.y - start.y) * dy) / length2))
        candidate = Point(start.x + fraction * dx, start.y + fraction * dy)
        distance = hypot(candidate.x - point.x, candidate.y - point.y)
        if best is None or distance < best[0]:
            best = distance, degrees(atan2(dy, dx)) % 360
    assert best is not None
    return best[1]
