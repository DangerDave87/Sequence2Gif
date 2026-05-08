from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .cli import build_convert_parser, run_convert_command
from .ui import MainWindow


def resource_path(*parts: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base_path.joinpath(*parts)


def run(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="Sequence to GIF")
    subparsers = parser.add_subparsers(dest="command")
    build_convert_parser(subparsers)
    parsed = parser.parse_args(args)

    if parsed.command == "convert":
        return run_convert_command(parsed)

    app = QApplication(sys.argv if argv is None else [sys.argv[0], *args])
    app.setApplicationName("Sequence to GIF")
    icon_path = resource_path("assets", "app_icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    return app.exec()
