"""Grille d'accueil des 20 classes avec recherche par effet, sort ou catégorie."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from bworkgrimoire.icon_cache import IconCache
from bworkgrimoire.models import BreedInfo, normalize_text
from bworkgrimoire.repository import SpellRepository
from bworkgrimoire.ui.flow_layout import FlowLayout

HOME_TAGS = (
    "Tous",
    "Érosion",
    "Pesanteur",
    "Débuff",
    "Invulnérable",
    "Bouclier",
    "Soin",
    "Placement",
    "Retrait PA/PM",
    "Invocation",
    "Boost",
)


class ClassGridWidget(QWidget):
    """Affiche les 20 classes cliquables avec recherche et filtres par mécanique."""

    # (breed_id, search_query_to_forward, tag_to_forward)
    breed_selected = Signal(int, str, str)

    def __init__(
        self,
        repo: SpellRepository,
        icon_cache: IconCache,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._repo = repo
        self._icon_cache = icon_cache
        self._selected_tag = "Tous"
        self._buttons_by_url: dict[str, list[QToolButton]] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(7)

        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        self._search = QLineEdit()
        self._search.setPlaceholderText(
            "Chercher une classe, un sort ou un effet (ex. Ouginak, pesanteur, érosion, débuff)..."
        )
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(lambda _txt: self._rebuild_grid())
        search_row.addWidget(self._search, 1)

        reset_btn = QPushButton("Réinitialiser")
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self.reset_filters)
        search_row.addWidget(reset_btn)
        layout.addLayout(search_row)

        # Barre de catégories wrapée automatiquement
        tags_container = QWidget()
        tags_flow = FlowLayout(tags_container, margin=0, spacing=5)
        self._tag_buttons: dict[str, QPushButton] = {}
        for tag in HOME_TAGS:
            label = "Toutes" if tag == "Tous" else tag
            btn = QPushButton(label)
            btn.setObjectName("FilterPill")
            btn.setCheckable(True)
            btn.setChecked(tag == "Tous")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, t=tag: self._select_tag(t))
            tags_flow.addWidget(btn)
            self._tag_buttons[tag] = btn
        layout.addWidget(tags_container)

        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("MutedLabel")
        layout.addWidget(self._status_lbl)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._grid_container = QWidget()
        self._grid = QGridLayout(self._grid_container)
        self._grid.setContentsMargins(2, 2, 2, 2)
        self._grid.setSpacing(7)
        self._scroll.setWidget(self._grid_container)
        layout.addWidget(self._scroll, 1)

        self._icon_cache.icon_ready.connect(self._on_icon_ready)
        self._rebuild_grid()

    def focus_search(self) -> None:
        self._search.setFocus()
        self._search.selectAll()

    def reset_filters(self) -> None:
        self._search.blockSignals(True)
        self._search.clear()
        self._search.blockSignals(False)
        self._select_tag("Tous", refresh=False)
        self._rebuild_grid()

    def _select_tag(self, tag: str, refresh: bool = True) -> None:
        self._selected_tag = tag
        for name, btn in self._tag_buttons.items():
            btn.setChecked(name == tag)
        if refresh:
            self._rebuild_grid()

    def _clear_grid(self) -> None:
        self._buttons_by_url.clear()
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _rebuild_grid(self) -> None:
        self._clear_grid()
        query = self._search.text().strip()
        results = self._repo.filter_breeds(query=query, tag=self._selected_tag)

        if query or self._selected_tag != "Tous":
            parts = []
            if self._selected_tag != "Tous":
                parts.append(f"catégorie « {self._selected_tag} »")
            if query:
                parts.append(f"recherche « {query} »")
            self._status_lbl.setText(
                f"{len(results)} classe(s) trouvée(s) pour " + " + ".join(parts)
            )
            self._status_lbl.show()
        else:
            self._status_lbl.hide()

        if not results:
            empty = QLabel("Aucune classe ou sort ne correspond à cette recherche.")
            empty.setObjectName("MutedLabel")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid.addWidget(empty, 0, 0)
            return

        cols = 4
        for idx, (breed, hit_count) in enumerate(results):
            btn = self._make_breed_tile(breed, hit_count, query)
            self._grid.addWidget(btn, idx // cols, idx % cols)

        spacer = QWidget()
        self._grid.addWidget(spacer, (len(results) // cols) + 1, 0)
        self._grid.setRowStretch((len(results) // cols) + 1, 1)

    def _make_breed_tile(self, breed: BreedInfo, hit_count: int, query: str) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("ClassTile")
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        label = f"{breed.name}\n({hit_count} sort{'s' if hit_count > 1 else ''})" if hit_count > 0 else breed.name
        btn.setText(label)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(84 if hit_count > 0 else 76)
        btn.setMinimumWidth(115)
        btn.setIconSize(QSize(36, 36))
        btn.setToolTip(breed.tip or breed.description)

        def on_click(_checked: bool = False, target: BreedInfo = breed) -> None:
            # Si l'utilisateur cherchait le nom de la classe ("ougi"), on affiche tous ses sorts.
            q_norm = normalize_text(query)
            forward_query = "" if (q_norm and q_norm in normalize_text(target.name)) else query
            self.breed_selected.emit(target.id, forward_query, self._selected_tag)

        btn.clicked.connect(on_click)

        if breed.img_url:
            pixmap = self._icon_cache.get_pixmap(breed.img_url)
            if pixmap is not None:
                btn.setIcon(QIcon(pixmap))
            else:
                self._buttons_by_url.setdefault(breed.img_url, []).append(btn)
        return btn

    def _on_icon_ready(self, url: str, pixmap: QPixmap) -> None:
        for btn in self._buttons_by_url.get(url, []):
            if isValid(btn):
                btn.setIcon(QIcon(pixmap))
