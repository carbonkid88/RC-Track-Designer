"""Vector print, preview and PDF support for track projects."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFontDatabase,
    QPainter,
    QPageLayout,
    QPageSize,
    QPen,
)
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrintPreviewWidget
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .model import Point, TrackProject
from .planning import draw_planning_object
from .rendering import (
    connection_bridge_polygon,
    element_centerline_path,
    element_filled_shape,
)


@dataclass
class PrintOptions:
    paper_size: str = "A4"
    orientation: str = "landscape"
    show_grid: bool = True
    grayscale: bool = False
    show_title: bool = True
    show_dimensions: bool = True


@dataclass(frozen=True)
class RenderMetrics:
    content_rect: QRectF
    layout_rect: QRectF
    units_per_metre: float
    grid_step_metres: float


def configure_printer(printer: QPrinter, options: PrintOptions) -> None:
    page_id = (
        QPageSize.PageSizeId.A3
        if options.paper_size == "A3"
        else QPageSize.PageSizeId.A4
    )
    printer.setPageSize(QPageSize(page_id))
    printer.setPageOrientation(
        QPageLayout.Orientation.Landscape
        if options.orientation == "landscape"
        else QPageLayout.Orientation.Portrait
    )
    printer.setColorMode(
        QPrinter.ColorMode.GrayScale
        if options.grayscale
        else QPrinter.ColorMode.Color
    )


def _grid_step(units_per_metre: float, dpi: float) -> float:
    """Choose a readable grid without changing the metre-based geometry."""
    minimum_cell = max(4.0, dpi * 0.10)  # roughly 2.5 mm on paper
    for step in (1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0):
        if step * units_per_metre >= minimum_cell:
            return step
    return 200.0


def render_project(
    painter: QPainter,
    target_rect: QRectF,
    project: TrackProject,
    options: PrintOptions,
    *,
    title: str = "",
    tr=lambda source, **values: source.format(**values),
    dpi: float = 96.0,
) -> RenderMetrics:
    """Render a project as clean vector artwork into ``target_rect``.

    The function deliberately accepts no canvas state. Selection, zoom, pan,
    connector markers and other editor-only state therefore cannot leak into
    print or PDF output.
    """
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.fillRect(target_rect, QColor("#ffffff"))

    margin = max(12.0, dpi * 0.20)
    minimum_text_px = max(10.0, dpi * 9.0 / 72.0)
    header_lines: list[str] = []
    if options.show_title:
        header_lines.append(title or tr("Untitled"))
    if options.show_dimensions:
        header_lines.append(
            tr(
                "Track area: {length:g} m × {width:g} m",
                length=project.hall_length,
                width=project.hall_width,
            )
        )
    header_height = (
        len(header_lines) * minimum_text_px * 1.35 + margin * 0.35
        if header_lines
        else 0.0
    )
    content = target_rect.adjusted(margin, margin + header_height, -margin, -margin)
    if content.width() <= 0 or content.height() <= 0:
        painter.restore()
        raise ValueError(tr("The printable page area is too small."))

    scale = min(
        content.width() / project.hall_length,
        content.height() / project.hall_width,
    )
    layout_width = project.hall_length * scale
    layout_height = project.hall_width * scale
    layout = QRectF(
        content.left() + (content.width() - layout_width) / 2,
        content.top() + (content.height() - layout_height) / 2,
        layout_width,
        layout_height,
    )

    def map_point(point: Point) -> QPointF:
        return QPointF(
            layout.left() + point.x * scale,
            layout.top() + (project.hall_width - point.y) * scale,
        )

    indoor = project.editor_mode == "indoor"
    if options.grayscale:
        hall_color = QColor("#ffffff")
        grid_color = QColor("#d0d0d0")
        track_color = QColor("#202020")
        boundary_color = QColor("#303030")
        centerline_color = QColor("#ffffff")
    else:
        hall_color = QColor("#34383E" if indoor else "#f8f8f5")
        grid_color = QColor("#ffffff" if indoor else "#d6dbe0")
        if indoor:
            grid_color.setAlpha(58)
        track_color = QColor("#5d636b")
        boundary_color = QColor("#F4CC2E")
        centerline_color = QColor("#ffffff")

    painter.fillRect(layout, hall_color)
    painter.save()
    painter.setClipRect(layout)
    grid_step = _grid_step(scale, dpi)
    if options.show_grid:
        grid_pen_width = max(0.35, dpi * 0.25 / 25.4)
        painter.setPen(QPen(grid_color, grid_pen_width))
        x = 0.0
        while x <= project.hall_length + 1e-9:
            point = map_point(Point(x, 0))
            painter.drawLine(
                QPointF(point.x(), layout.top()),
                QPointF(point.x(), layout.bottom()),
            )
            x += grid_step
        y = 0.0
        while y <= project.hall_width + 1e-9:
            point = map_point(Point(0, y))
            painter.drawLine(
                QPointF(layout.left(), point.y()),
                QPointF(layout.right(), point.y()),
            )
            y += grid_step

    if options.grayscale and not indoor:
        # Draw a slightly wider dark silhouette, then overlay the complete
        # road in white.  This leaves only the outer contour, including at
        # overlaps, without fragile boolean unions of complex painter paths.
        contour_width = max(0.6, dpi * 0.35 / 25.4)
        bridge_depth = max(2.0, contour_width * 2.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        for element in project.elements:
            painter.drawPath(
                element_filled_shape(
                    element,
                    map_point,
                    scale,
                    width_adjustment=-2 * contour_width,
                )
            )
        for connection in project.connections:
            painter.drawPolygon(
                connection_bridge_polygon(
                    project,
                    connection,
                    map_point,
                    scale,
                    half_depth=bridge_depth + contour_width,
                    half_width_inset=-contour_width,
                )
            )

        painter.setBrush(QColor("#ffffff"))
        for element in project.elements:
            painter.drawPath(element_filled_shape(element, map_point, scale))
        for connection in project.connections:
            painter.drawPolygon(
                connection_bridge_polygon(
                    project,
                    connection,
                    map_point,
                    scale,
                    half_depth=bridge_depth,
                )
            )
        centerline_width = max(0.8, dpi * 0.30 / 25.4)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(
            QPen(track_color, centerline_width, Qt.PenStyle.DashLine)
        )
        for element in project.elements:
            painter.drawPath(element_centerline_path(element, map_point, scale))
    else:
        painter.setPen(Qt.PenStyle.NoPen)
        for element in project.elements:
            painter.setBrush(
                boundary_color if element.element_type == "boundary" else track_color
            )
            painter.drawPath(element_filled_shape(element, map_point, scale))

        bridge_depth = max(0.6, dpi * 0.20 / 25.4)
        for connection in project.connections:
            first = project.element_by_id(connection.first.element_id)
            if first is None:
                continue
            painter.setBrush(
                boundary_color if first.element_type == "boundary" else track_color
            )
            painter.drawPolygon(
                connection_bridge_polygon(
                    project,
                    connection,
                    map_point,
                    scale,
                    half_depth=bridge_depth,
                )
            )

        centerline_width = max(0.35, dpi * 0.22 / 25.4)
        for element in project.elements:
            if element.element_type == "boundary":
                continue
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(
                QPen(centerline_color, centerline_width, Qt.PenStyle.DashLine)
            )
            painter.drawPath(element_centerline_path(element, map_point, scale))
    for item in project.planning_objects:
        draw_planning_object(
            painter, item, map_point, scale, grayscale=options.grayscale,
            number=project.starting_grid_number(item),
        )
    painter.restore()

    border_width = max(0.5, dpi * 0.30 / 25.4)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor("#202020"), border_width))
    painter.drawRect(layout)

    if header_lines:
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
        font.setPixelSize(round(minimum_text_px))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#202020"))
        header = QRectF(
            content.left(),
            target_rect.top() + margin * 0.45,
            content.width(),
            header_height,
        )
        painter.drawText(
            header,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "\n".join(header_lines),
        )

    painter.restore()
    return RenderMetrics(content, layout, scale, grid_step)


def render_project_to_printer(
    printer: QPrinter,
    project: TrackProject,
    options: PrintOptions,
    *,
    title: str = "",
    tr=lambda source, **values: source.format(**values),
) -> RenderMetrics:
    configure_printer(printer, options)
    painter = QPainter()
    if not painter.begin(printer):
        raise OSError(tr("The print device could not be opened."))
    try:
        page = QRectF(printer.pageLayout().paintRectPixels(printer.resolution()))
        return render_project(
            painter,
            page,
            project,
            options,
            title=title,
            tr=tr,
            dpi=float(printer.resolution()),
        )
    finally:
        painter.end()


class PrintSettingsWidget(QWidget):
    changed = Signal()

    def __init__(self, options: PrintOptions, tr, parent=None) -> None:
        super().__init__(parent)
        self._tr = tr
        form = QFormLayout(self)
        self.paper_combo = QComboBox()
        self.paper_combo.addItem("A4", "A4")
        self.paper_combo.addItem("A3", "A3")
        self.paper_combo.setCurrentIndex(
            max(0, self.paper_combo.findData(options.paper_size))
        )
        self.orientation_combo = QComboBox()
        self.orientation_combo.addItem(tr("Landscape"), "landscape")
        self.orientation_combo.addItem(tr("Portrait"), "portrait")
        self.orientation_combo.setCurrentIndex(
            max(0, self.orientation_combo.findData(options.orientation))
        )
        self.grid_check = QCheckBox(tr("Show grid"))
        self.grid_check.setChecked(options.show_grid)
        self.grayscale_check = QCheckBox(tr("Ink-saving grayscale"))
        self.grayscale_check.setChecked(options.grayscale)
        self.title_check = QCheckBox(tr("Show project title"))
        self.title_check.setChecked(options.show_title)
        self.dimensions_check = QCheckBox(tr("Show track area dimensions"))
        self.dimensions_check.setChecked(options.show_dimensions)
        form.addRow(tr("Paper size:"), self.paper_combo)
        form.addRow(tr("Orientation:"), self.orientation_combo)
        form.addRow(self.grid_check)
        form.addRow(self.grayscale_check)
        form.addRow(self.title_check)
        form.addRow(self.dimensions_check)
        for control in (
            self.paper_combo,
            self.orientation_combo,
            self.grid_check,
            self.grayscale_check,
            self.title_check,
            self.dimensions_check,
        ):
            signal = (
                control.currentIndexChanged
                if isinstance(control, QComboBox)
                else control.toggled
            )
            signal.connect(self.changed)

    def options(self) -> PrintOptions:
        return PrintOptions(
            paper_size=str(self.paper_combo.currentData()),
            orientation=str(self.orientation_combo.currentData()),
            show_grid=self.grid_check.isChecked(),
            grayscale=self.grayscale_check.isChecked(),
            show_title=self.title_check.isChecked(),
            show_dimensions=self.dimensions_check.isChecked(),
        )


class PrintOptionsDialog(QDialog):
    def __init__(self, options: PrintOptions, tr, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Print settings"))
        layout = QVBoxLayout(self)
        self.settings_widget = PrintSettingsWidget(options, tr, self)
        layout.addWidget(self.settings_widget)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def options(self) -> PrintOptions:
        return self.settings_widget.options()


class LayoutPrintPreviewDialog(QDialog):
    """Print preview whose settings update the preview immediately."""

    def __init__(
        self,
        project: TrackProject,
        options: PrintOptions,
        title: str,
        tr,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Print preview"))
        self.resize(1050, 720)
        self.project = project
        self._options = replace(options)
        self._title = title
        self._tr = tr
        self.printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        configure_printer(self.printer, self._options)

        outer = QVBoxLayout(self)
        content = QHBoxLayout()
        self.settings_widget = PrintSettingsWidget(
            self._options, tr, self
        )
        self.settings_widget.setMaximumWidth(280)
        content.addWidget(self.settings_widget)
        self.preview = QPrintPreviewWidget(self.printer, self)
        self.preview.paintRequested.connect(self._paint_requested)
        content.addWidget(self.preview, 1)
        outer.addLayout(content, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.print_button = QPushButton(tr("Print…"), self)
        buttons.addButton(self.print_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)
        self.print_button.clicked.connect(self._print)
        outer.addWidget(buttons)
        self.settings_widget.changed.connect(self._settings_changed)

    def options(self) -> PrintOptions:
        return replace(self._options)

    def _settings_changed(self) -> None:
        self._options = self.settings_widget.options()
        configure_printer(self.printer, self._options)
        self.preview.updatePreview()

    def _paint_requested(self, printer: QPrinter) -> None:
        try:
            render_project_to_printer(
                printer,
                self.project,
                self._options,
                title=self._title,
                tr=self._tr,
            )
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                self._tr("Print failed"),
                str(error),
            )

    def _print(self) -> None:
        dialog = QPrintDialog(self.printer, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.preview.print_()


def pdf_printer(path: str | Path, options: PrintOptions) -> QPrinter:
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(path))
    configure_printer(printer, options)
    return printer
