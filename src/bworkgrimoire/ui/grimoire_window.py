"""Grimoire overlay : fenêtre « livre ouvert » (interface web) + widget « livre fermé » natif.

- La fenêtre affiche data/web/grimoire.html dans un QWebEngineView transparent, sans cadre,
  toujours au-dessus du jeu. La page pilote la fenêtre via QWebChannel (déplacer, redimensionner
  par les coins haut-gauche / bas-droit, refermer le livre).
- Refermé, le grimoire devient un petit livre flottant : clic = rouvrir, glisser = déplacer,
  clic droit = menu (Ouvrir / Quitter).
- Position, taille et état (ouvert/fermé) sont mémorisés entre deux lancements.
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QRect, QRectF, QSettings, QSize, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QColor, QGuiApplication, QIcon, QMouseEvent, QPainter, QPixmap, QRadialGradient
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QVBoxLayout, QWidget

from bworkgrimoire.icon_cache import default_cache_dir
from bworkgrimoire.repository import SpellRepository, default_data_dir
from bworkgrimoire.web_page import web_dir, write_page

OVERLAY_FLAGS = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint
DEFAULT_SIZE = QSize(480, 780)
MIN_SIZE = QSize(340, 420)
# Centre du bouton « livre ouvert » dans la barre de titre de la page (px, depuis le coin haut-gauche)
BOOK_BUTTON_CENTER = QPoint(36, 25)
BOOK_WIDGET_SIZE = 76
BOOK_DRAW_SIZE = 62


def user_cache_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".cache"))
    folder = base / "Grimoire"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def book_svg_path() -> Path:
    return web_dir() / "book_closed.svg"


def book_icon() -> QIcon:
    """Icône d'application (barre des tâches, zone de notification) : le grimoire fermé."""
    renderer = QSvgRenderer(str(book_svg_path()))
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128):
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pix)
    return icon


class _Bridge(QObject):
    """Objet exposé à la page (window.bridge) via QWebChannel."""

    collapse_requested = Signal()
    move_requested = Signal()
    resize_requested = Signal(str)

    @Slot()
    def collapse(self) -> None:
        self.collapse_requested.emit()

    @Slot()
    def startMove(self) -> None:  # noqa: N802 - nom appelé depuis le JavaScript
        self.move_requested.emit()

    @Slot(str)
    def startResize(self, corner: str) -> None:  # noqa: N802
        self.resize_requested.emit(corner)


class GrimoireWindow(QWidget):
    """Fenêtre « livre ouvert » contenant l'interface du grimoire."""

    def __init__(self, page_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent, OVERLAY_FLAGS)
        self.setWindowTitle("Grimoire")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(MIN_SIZE)
        self.resize(DEFAULT_SIZE)

        self.view = QWebEngineView(self)
        self.view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.view.setStyleSheet("background: transparent;")
        self.view.page().setBackgroundColor(Qt.GlobalColor.transparent)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)

        self.bridge = _Bridge(self)
        self._channel = QWebChannel(self)
        self._channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self._channel)
        self.bridge.move_requested.connect(self._start_move)
        self.bridge.resize_requested.connect(self._start_resize)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.view.load(QUrl.fromLocalFile(str(page_path)))

    def _start_move(self) -> None:
        handle = self.windowHandle()
        if handle is not None:
            handle.startSystemMove()

    def _start_resize(self, corner: str) -> None:
        edges = (
            Qt.Edge.TopEdge | Qt.Edge.LeftEdge if corner == "tl" else Qt.Edge.BottomEdge | Qt.Edge.RightEdge
        )
        handle = self.windowHandle()
        if handle is not None:
            handle.startSystemResize(edges)

    def play_open_animation(self) -> None:
        self.view.page().runJavaScript("window.playOpen && window.playOpen();")


class BookWidget(QWidget):
    """Petit grimoire fermé flottant au-dessus du jeu."""

    open_requested = Signal()
    quit_requested = Signal()
    moved = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, OVERLAY_FLAGS)
        self.setWindowTitle("Grimoire")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(BOOK_WIDGET_SIZE, BOOK_WIDGET_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Ouvrir le grimoire")
        self._renderer = QSvgRenderer(str(book_svg_path()), self)
        self._hover = False
        self._press: QPoint | None = None
        self._origin = QPoint()
        self._dragging = False

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QRectF(self.rect()).center()
        size = BOOK_DRAW_SIZE * (1.07 if self._hover or self._dragging else 1.0)
        if self._hover:
            glow = QRadialGradient(center, BOOK_WIDGET_SIZE / 2)
            glow.setColorAt(0.0, QColor(255, 176, 46, 70))
            glow.setColorAt(1.0, QColor(255, 176, 46, 0))
            painter.setBrush(glow)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(self.rect()))
        target = QRectF(center.x() - size / 2, center.y() - size / 2, size, size)
        self._renderer.render(painter, target)

    def enterEvent(self, _event) -> None:  # noqa: N802
        self._hover = True
        self.update()

    def leaveEvent(self, _event) -> None:  # noqa: N802
        self._hover = False
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.globalPosition().toPoint()
            self._origin = self.pos()
            self._dragging = False
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._press is None:
            return
        delta = event.globalPosition().toPoint() - self._press
        if not self._dragging and delta.manhattanLength() < 5:
            return
        self._dragging = True
        self.move(self._origin + delta)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._press is None:
            return
        was_drag = self._dragging
        self._press = None
        self._dragging = False
        self.update()
        if was_drag:
            self.moved.emit()
        else:
            self.open_requested.emit()

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        menu = QMenu(self)
        menu.addAction("Ouvrir le grimoire", self.open_requested.emit)
        menu.addSeparator()
        menu.addAction("Quitter Grimoire", self.quit_requested.emit)
        menu.exec(event.globalPos())


def _clamp_to_screen(rect: QRect) -> QRect:
    screen = QGuiApplication.screenAt(rect.center()) or QGuiApplication.primaryScreen()
    area = screen.availableGeometry()
    x = max(area.left(), min(rect.x(), area.right() - rect.width() + 1))
    y = max(area.top(), min(rect.y(), area.bottom() - rect.height() + 1))
    return QRect(x, y, rect.width(), rect.height())


class GrimoireController(QObject):
    """Orchestre la fenêtre, le livre fermé, la zone de notification et la mémorisation."""

    def __init__(self, repo: SpellRepository, enable_tray: bool = True, settings: QSettings | None = None) -> None:
        super().__init__()
        self._settings = settings or QSettings("Grimoire", "Grimoire")
        page = write_page(
            repo,
            user_cache_dir() / "grimoire.html",
            host="qt",
            data_dir=default_data_dir(),
            extra_icon_dirs=[default_cache_dir()],
        )
        self.window = GrimoireWindow(page)
        self.book = BookWidget()
        icon = book_icon()
        self.window.setWindowIcon(icon)
        self.book.setWindowIcon(icon)
        QApplication.setWindowIcon(icon)

        self.window.bridge.collapse_requested.connect(self.collapse)
        self.book.open_requested.connect(self.expand)
        self.book.moved.connect(self._save)
        self.book.quit_requested.connect(QApplication.quit)

        self._restore_geometry()
        self._tray: QSystemTrayIcon | None = None
        if enable_tray and QSystemTrayIcon.isSystemTrayAvailable():
            self._setup_tray(icon)
        QApplication.instance().aboutToQuit.connect(self._save)

    # --- état -----------------------------------------------------------------
    def _restore_geometry(self) -> None:
        geometry = self._settings.value("window/geometry")
        if geometry is not None:
            self.window.restoreGeometry(geometry)
        else:
            area = QGuiApplication.primaryScreen().availableGeometry()
            self.window.move(area.right() - DEFAULT_SIZE.width() - 40, area.top() + 60)
        self.window.setGeometry(_clamp_to_screen(self.window.geometry()))
        book_pos = self._settings.value("book/pos")
        if isinstance(book_pos, QPoint):
            self.book.move(book_pos)
        else:
            self.book.move(self._book_pos_for_window())

    def _save(self) -> None:
        self._settings.setValue("window/geometry", self.window.saveGeometry())
        self._settings.setValue("book/pos", self.book.pos())
        self._settings.setValue("book/collapsed", self.book.isVisible())

    def start(self) -> None:
        collapsed = str(self._settings.value("book/collapsed", "false")).lower() == "true"
        if collapsed:
            self.book.move(_clamp_to_screen(self.book.geometry()).topLeft())
            self.book.show()
        else:
            self.window.show()

    # --- livre ouvert / fermé ----------------------------------------------------
    def _book_pos_for_window(self) -> QPoint:
        half = BOOK_WIDGET_SIZE // 2
        return self.window.pos() + BOOK_BUTTON_CENTER - QPoint(half, half)

    def collapse(self) -> None:
        self.book.move(_clamp_to_screen(QRect(self._book_pos_for_window(), self.book.size())).topLeft())
        self.window.hide()
        self.book.show()
        self.book.raise_()
        self._save()

    def expand(self) -> None:
        half = BOOK_WIDGET_SIZE // 2
        target = self.book.pos() + QPoint(half, half) - BOOK_BUTTON_CENTER
        self.window.setGeometry(_clamp_to_screen(QRect(target, self.window.size())))
        self.book.hide()
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()
        QTimer.singleShot(0, self.window.play_open_animation)
        self._save()

    def toggle(self) -> None:
        if self.window.isVisible():
            self.collapse()
        else:
            self.expand()

    # --- zone de notification ----------------------------------------------------
    def _setup_tray(self, icon: QIcon) -> None:
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip("Grimoire — sorts Dofus")
        menu = QMenu()
        toggle = QAction("Ouvrir / refermer le grimoire", menu)
        toggle.triggered.connect(self.toggle)
        quit_action = QAction("Quitter", menu)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(toggle)
        menu.addSeparator()
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(
            lambda reason: self.toggle() if reason == QSystemTrayIcon.ActivationReason.Trigger else None
        )
        self._tray.show()
        self._tray_menu = menu
