"""Anwendungseinstiegspunkt."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from . import __version__
from .ui import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setOrganizationName("RC Track Designer")
    app.setOrganizationDomain("rc-track-designer.org")
    app.setApplicationName("RC Track Designer")
    app.setApplicationVersion(__version__)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
