"""Anwendungseinstiegspunkt."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import __release_name__
from .ui import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setOrganizationName("RC Track Designer")
    app.setOrganizationDomain("rc-track-designer.org")
    app.setApplicationName("RC Track Designer")
    app.setApplicationVersion(__release_name__)
    app.setWindowIcon(QIcon(str(Path(__file__).with_name("assets") / "software_icon_candidate.png")))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
