"""Собирает архив виджета для загрузки в amoCRM: dist/widget.zip.

Файлы кладутся в корень архива (manifest.json, script.js, i18n/, images/),
как требует amoCRM. Перед упаковкой проверяется, что JSON-файлы валидны,
а обязательные файлы на месте.

Запуск: python scripts/build_widget.py
"""

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "amocrm_widget"
DIST = ROOT / "dist" / "widget.zip"  # amoCRM ожидает именно это имя
REQUIRED = [
    "manifest.json",
    "script.js",
    "style.css",
    "images/logo_min.png",
    "images/logo_medium.png",
    "images/logo_main.png",
    "images/logo_small.png",
    "images/logo.png",
]


def main() -> int:
    missing = [name for name in REQUIRED if not (SRC / name).is_file()]
    if missing:
        print(f"Нет обязательных файлов: {', '.join(missing)}", file=sys.stderr)
        return 1

    manifest = json.loads((SRC / "manifest.json").read_text(encoding="utf-8"))
    for locale in manifest["widget"]["locale"]:
        path = SRC / "i18n" / f"{locale}.json"
        if not path.is_file():
            print(f"Нет файла локализации {path.relative_to(ROOT)}", file=sys.stderr)
            return 1
        json.loads(path.read_text(encoding="utf-8"))

    DIST.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(DIST, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(SRC.rglob("*")):
            if path.is_file() and not path.name.startswith("."):
                archive.write(path, path.relative_to(SRC).as_posix())
    print(f"Готово: {DIST.relative_to(ROOT)} (версия {manifest['widget']['version']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
