"""Einfache, zur Laufzeit erweiterbare JSON-Übersetzungen."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QStandardPaths


BUILTIN_LOCALES = Path(__file__).with_name("locales")


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    path: Path | None = None


class TranslationManager:
    def __init__(self, language: str = "de") -> None:
        self.language = language
        self._catalog: dict[str, str] = {}
        self.set_language(language)

    @staticmethod
    def user_locale_dir() -> Path:
        root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        return root / "locales"

    def available_languages(self) -> list[Language]:
        result = {"en": Language("en", "English")}
        for directory in (BUILTIN_LOCALES, self.user_locale_dir()):
            if not directory.exists():
                continue
            for path in directory.glob("*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    code = str(data["code"])
                    result[code] = Language(code, str(data.get("name", code)), path)
                except (OSError, ValueError, KeyError, TypeError):
                    continue
        return sorted(result.values(), key=lambda item: item.name.casefold())

    def set_language(self, code: str) -> None:
        self.language = code
        self._catalog = {}
        if code == "en":
            return
        language = next((item for item in self.available_languages() if item.code == code), None)
        if language and language.path:
            data = json.loads(language.path.read_text(encoding="utf-8"))
            self._catalog = {str(key): str(value) for key, value in data.get("translations", {}).items()}

    def tr(self, source: str, **values) -> str:
        text = self._catalog.get(source, source)
        return text.format(**values) if values else text

