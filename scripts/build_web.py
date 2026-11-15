"""Exporte la version Web / Web Overlay statique de Grimoire dans dist/web/."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bworkgrimoire.repository import SpellRepository  # noqa: E402
from bworkgrimoire.web_page import export_web_bundle  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère le site Web statique de Grimoire.")
    parser.add_argument("--out", type=Path, default=ROOT / "dist" / "web", help="Dossier de sortie.")
    args = parser.parse_args()

    repo = SpellRepository.load_from_files()
    index_path = export_web_bundle(repo, args.out)
    print(f"Web bundle generated: {index_path}")


if __name__ == "__main__":
    main()
