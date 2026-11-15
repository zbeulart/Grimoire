"""Fenêtre overlay principale : compacte, déplaçable, toujours au-dessus et épinglable."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QKeySequence, QMouseEvent, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSizeGrip,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from bworkgrimoire.icon_cache import IconCache
from bworkgrimoire.repository import SpellRepository
from bworkgrimoire.ui.class_grid import ClassGridWidget
from bworkgrimoire.ui.spell_view import SpellViewWidget
from bworkgrimoire.ui.styles import OVERLAY_QSS


class OverlayWindow(QMainWindow):
    """Fenêtre overlay BworkGrimoire affichant les classes et sorts Dofus."""

    def __init__(
        self,
        repo: SpellRepository,
        icon_cache: IconCache | None = None,
        enable_tray: bool = True,
    ) -> None:
        super().__init__()
        self._repo = repo
        self._icon_cache = icon_cache or IconCache(parent=self)
        self._drag_pos: QPoint | None = None
        self._always_on_top = True
        self._pinned_breed_ids: list[int] = []
        self._current_breed_id: int | None = None

        self.setWindowTitle("BworkGrimoire")
        self.resize(740, 740)
        self.setMinimumSize(500, 480)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._apply_window_flags()

        root_card = QWidget()
        root_card.setObjectName("RootCard")
        root_card.setStyleSheet(OVERLAY_QSS)
        self.setCentralWidget(root_card)

        outer = QVBoxLayout(root_card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Barre de titre personnalisée (déplaçable)
        self._title_bar = QWidget()
        self._title_bar.setObjectName("TitleBar")
        title_layout = QHBoxLayout(self._title_bar)
        title_layout.setContentsMargins(10, 6, 8, 6)
        title_layout.setSpacing(6)

        brand = QLabel("BworkGrimoire")
        brand.setStyleSheet("font-size: 13px; font-weight: 700; color: #a3e635;")
        title_layout.addWidget(brand)

        self._tabs_layout = QHBoxLayout()
        self._tabs_layout.setSpacing(4)
        title_layout.addLayout(self._tabs_layout)
        title_layout.addStretch(1)

        self._top_btn = QPushButton("📌 Top")
        self._top_btn.setObjectName("TitleBtn")
        self._top_btn.setCheckable(True)
        self._top_btn.setChecked(True)
        self._top_btn.setToolTip("Garder la fenêtre au-dessus de Dofus")
        self._top_btn.clicked.connect(self._toggle_on_top)
        title_layout.addWidget(self._top_btn)

        hide_btn = QPushButton("—")
        hide_btn.setObjectName("TitleBtn")
        hide_btn.setToolTip("Réduire dans la zone de notification")
        hide_btn.clicked.connect(self.hide)
        title_layout.addWidget(hide_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("TitleBtn")
        close_btn.setToolTip("Fermer BworkGrimoire")
        close_btn.clicked.connect(QApplication.quit)
        title_layout.addWidget(close_btn)
        outer.addWidget(self._title_bar)

        # Pages : Grille des classes (0) <-> Fiche de classe (1)
        self._stack = QStackedWidget()
        self._class_grid = ClassGridWidget(self._repo, self._icon_cache)
        self._spell_view = SpellViewWidget(self._icon_cache)
        self._class_grid.breed_selected.connect(self.open_breed)
        self._spell_view.back_requested.connect(self.show_home)
        self._spell_view.pin_requested.connect(self.toggle_pin_breed)
        self._stack.addWidget(self._class_grid)
        self._stack.addWidget(self._spell_view)
        outer.addWidget(self._stack, 1)

        # Pied de page (crédit obligatoire DofusDB + poignée de redimensionnement)
        footer = QHBoxLayout()
        footer.setContentsMargins(10, 4, 4, 6)
        credit = QLabel("Projet communautaire non affilié à Ankama — Données : DofusDB")
        credit.setObjectName("MutedLabel")
        footer.addWidget(credit, 1)
        grip = QSizeGrip(root_card)
        footer.addWidget(grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        outer.addLayout(footer)

        # Raccourci interne Échap pour revenir rapidement à la grille
        esc_shortcut = QShortcut(QKeySequence("Escape"), self)
        esc_shortcut.activated.connect(self.show_home)

        self._rebuild_pin_tabs()
        self._tray: QSystemTrayIcon | None = None
        if enable_tray and QSystemTrayIcon.isSystemTrayAvailable():
            self._setup_tray()

    def _apply_window_flags(self) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        if self._always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def _toggle_on_top(self, checked: bool) -> None:
        self._always_on_top = checked
        was_visible = self.isVisible()
        self._apply_window_flags()
        if was_visible:
            self.show()

    def _setup_tray(self) -> None:
        self._tray = QSystemTrayIcon(self)
        self._tray.setToolTip("BworkGrimoire — Lexique sorts Dofus")
        menu = QMenu()
        toggle_action = QAction("Afficher / Masquer", self)
        toggle_action.triggered.connect(self.toggle_visibility)
        quit_action = QAction("Quitter", self)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(toggle_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(
            lambda reason: self.toggle_visibility()
            if reason == QSystemTrayIcon.ActivationReason.Trigger
            else None
        )
        self._tray.show()

    def toggle_visibility(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def show_home(self) -> None:
        self._current_breed_id = None
        self._stack.setCurrentIndex(0)
        self._rebuild_pin_tabs()
        self._class_grid.focus_search()

    def open_breed(
        self,
        breed_id: int,
        initial_query: str = "",
        initial_tag: str = "Tous",
    ) -> None:
        breed = self._repo.get_breed(breed_id)
        if breed is None:
            return
        self._current_breed_id = breed_id
        self._spell_view.set_breed(
            breed,
            is_pinned=breed_id in self._pinned_breed_ids,
            initial_query=initial_query,
            initial_tag=initial_tag,
        )
        self._stack.setCurrentIndex(1)
        self._rebuild_pin_tabs()

    def toggle_pin_breed(self, breed_id: int) -> None:
        if breed_id in self._pinned_breed_ids:
            self._pinned_breed_ids.remove(breed_id)
        else:
            if len(self._pinned_breed_ids) >= 3:
                self._pinned_breed_ids.pop(0)
            self._pinned_breed_ids.append(breed_id)
        if self._current_breed_id == breed_id:
            self._spell_view.set_pinned_state(breed_id in self._pinned_breed_ids)
        self._rebuild_pin_tabs()

    def _rebuild_pin_tabs(self) -> None:
        while self._tabs_layout.count():
            item = self._tabs_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        home_btn = QPushButton("Classes")
        home_btn.setCheckable(True)
        home_btn.setChecked(self._stack.currentIndex() == 0)
        home_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        home_btn.clicked.connect(self.show_home)
        self._tabs_layout.addWidget(home_btn)

        for bid in self._pinned_breed_ids:
            breed = self._repo.get_breed(bid)
            if breed is None:
                continue
            tab = QPushButton(breed.name)
            tab.setCheckable(True)
            tab.setChecked(self._stack.currentIndex() == 1 and self._current_breed_id == bid)
            tab.setCursor(Qt.CursorShape.PointingHandCursor)
            tab.clicked.connect(lambda _=False, target=bid: self.open_breed(target))
            self._tabs_layout.addWidget(tab)

    # Déplacement de la fenêtre via la barre de titre
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and event.position().y() <= self._title_bar.height()
        ):
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)
