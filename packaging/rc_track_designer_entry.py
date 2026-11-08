"""PyInstaller entry point for the windowed Windows build."""

from rc_track_designer.app import main


if __name__ == "__main__":
    raise SystemExit(main())
