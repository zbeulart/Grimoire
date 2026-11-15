"""Cache disque et téléchargement asynchrone léger des icônes de classes et sorts."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QPixmap


def default_cache_dir() -> Path:
    """Retourne le dossier de cache utilisateur sous Windows (%LOCALAPPDATA%)."""
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".cache"))
    cache_dir = base / "BworkGrimoire" / "icons"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def bundled_icons_dir() -> Path | None:
    """Retourne le dossier data/icons si embarqué dans le package/repo."""
    import sys

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidate = Path(sys._MEIPASS) / "data" / "icons"  # type: ignore[attr-defined]
    else:
        candidate = Path(__file__).resolve().parents[2] / "data" / "icons"
    return candidate if candidate.exists() else None


class _IconSignals(QObject):
    loaded = Signal(str, bytes)


class _IconFetchTask(QRunnable):
    def __init__(self, url: str, target_path: Path, signals: _IconSignals) -> None:
        super().__init__()
        self.url = url
        self.target_path = target_path
        self.signals = signals

    def run(self) -> None:
        try:
            resp = httpx.get(
                self.url,
                timeout=8.0,
                headers={"User-Agent": "BworkGrimoire/0.1"},
                follow_redirects=True,
            )
            if resp.status_code == 200 and resp.content:
                self.target_path.write_bytes(resp.content)
                self.signals.loaded.emit(self.url, resp.content)
        except Exception:
            # En mode hors-ligne ou erreur réseau, on garde simplement le placeholder.
            pass


class IconCache(QObject):
    """Gère le cache mémoire + disque des icônes avec téléchargement non bloquant."""

    icon_ready = Signal(str, QPixmap)

    def __init__(self, cache_dir: Path | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cache_dir = cache_dir or default_cache_dir()
        self._bundled_dir = bundled_icons_dir()
        self._memory: dict[str, QPixmap] = {}
        self._pending: set[str] = set()
        self._signals = _IconSignals(self)
        self._signals.loaded.connect(self._on_loaded)
        self._pool = QThreadPool.globalInstance()

    @staticmethod
    def _filename_for(url: str) -> str:
        safe = url.rsplit("/", 1)[-1]
        return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in safe)

    def get_pixmap(self, url: str) -> QPixmap | None:
        """Retourne immédiatement le QPixmap en cache, sinon lance le fetch asynchrone."""
        if not url:
            return None
        if url in self._memory:
            return self._memory[url]

        filename = self._filename_for(url)
        for folder in (self._bundled_dir, self._cache_dir):
            if folder is None:
                continue
            local = folder / filename
            if local.exists():
                pixmap = QPixmap(str(local))
                if not pixmap.isNull():
                    self._memory[url] = pixmap
                    return pixmap

        if url not in self._pending:
            self._pending.add(url)
            task = _IconFetchTask(url, self._cache_dir / filename, self._signals)
            self._pool.start(task)
        return None

    def _on_loaded(self, url: str, raw_bytes: bytes) -> None:
        self._pending.discard(url)
        pixmap = QPixmap()
        if raw_bytes and pixmap.loadFromData(raw_bytes) and not pixmap.isNull():
            self._memory[url] = pixmap
            self.icon_ready.emit(url, pixmap)
