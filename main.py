"""Point d'entrée principal de Grimoire."""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# QtWebEngine doit être importé avant la création de la QApplication.
from bworkgrimoire.ui.grimoire_window import GrimoireController  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from bworkgrimoire.repository import SpellRepository  # noqa: E402


def main() -> int:
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Bworkshop.Grimoire.1")

    app = QApplication(sys.argv)
    app.setApplicationName("Grimoire")
    app.setQuitOnLastWindowClosed(False)

    repo = SpellRepository.load_from_files()
    controller = GrimoireController(repo)
    controller.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
