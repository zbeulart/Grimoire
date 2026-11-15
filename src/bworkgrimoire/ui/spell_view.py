"""Vue détaillée d'une classe : mode Grille 2 colonnes (compacte) + mode Liste + panneau détail."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from bworkgrimoire.icon_cache import IconCache
from bworkgrimoire.models import BreedInfo, SpellInfo, SpellVariantPair
from bworkgrimoire.repository import SpellRepository
from bworkgrimoire.ui.flow_layout import FlowLayout
from bworkgrimoire.ui.styles import ELEMENT_COLORS

ELEMENTS = ("Tous", "Feu", "Eau", "Air", "Terre", "Multi", "Utilitaire")
QUICK_TAGS = (
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


class _ClickableSpellPill(QFrame):
    """Pilule compacte cliquable représentant un sort dans la grille 2 colonnes."""

    clicked = Signal(object)

    def __init__(
        self,
        spell: SpellInfo,
        is_variant: bool,
        dimmed: bool,
        selected: bool,
        icon_cache: IconCache,
        icon_registry: dict[str, list[QLabel]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._spell = spell
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        color = ELEMENT_COLORS.get(spell.element, "#94a3b8")
        border_col = "#84cc16" if selected else "rgba(148, 163, 184, 42)"
        bg_col = "rgba(44, 52, 74, 235)" if selected else (
            "rgba(24, 27, 38, 120)" if dimmed else "rgba(31, 35, 50, 225)"
        )
        self.setStyleSheet(
            f"QFrame {{ background-color: {bg_col}; border: 1px solid {border_col}; "
            f"border-left: 3px solid {color}; border-radius: 6px; }}"
            f"QFrame:hover {{ border-color: #84cc16; }}"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(6, 5, 6, 5)
        row.setSpacing(7)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(30, 30)
        icon_lbl.setScaledContents(True)
        icon_lbl.setStyleSheet("border: none; background: rgba(15, 23, 42, 180); border-radius: 4px;")
        if spell.img_url:
            pix = icon_cache.get_pixmap(spell.img_url)
            if pix is not None:
                icon_lbl.setPixmap(pix)
            else:
                icon_registry.setdefault(spell.img_url, []).append(icon_lbl)
        row.addWidget(icon_lbl)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)

        name_lbl = QLabel(spell.name)
        name_lbl.setStyleSheet(
            f"border: none; background: transparent; font-size: 11.5px; font-weight: 700; "
            f"color: {'#64748b' if dimmed else '#f8fafc'};"
        )
        name_lbl.setWordWrap(False)
        text_col.addWidget(name_lbl)

        role = "Var" if is_variant else "Sort"
        cd_part = f" • CD {spell.cooldown}" if spell.cooldown > 0 else ""
        meta_lbl = QLabel(f"{role} • {spell.ap_cost} PA • {spell.format_range()}{cd_part}")
        meta_lbl.setStyleSheet(
            f"border: none; background: transparent; font-size: 10.5px; "
            f"color: {'#475569' if dimmed else '#94a3b8'};"
        )
        text_col.addWidget(meta_lbl)
        row.addLayout(text_col, 1)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._spell)
            event.accept()
            return
        super().mousePressEvent(event)


class SpellViewWidget(QWidget):
    """Affiche tous les sorts d'une classe avec recherche, filtres et 2 modes de vue."""

    back_requested = Signal()
    pin_requested = Signal(int)

    def __init__(
        self,
        icon_cache: IconCache,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._icon_cache = icon_cache
        self._breed: BreedInfo | None = None
        self._selected_element = "Tous"
        self._selected_tag = "Tous"
        self._view_mode = "grid"  # "grid" | "list"
        self._selected_spell: SpellInfo | None = None
        self._icon_labels: dict[str, list[QLabel]] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        # Barre supérieure : Retour + Classe + Mode Grille/Liste + Épingler
        header = QHBoxLayout()
        header.setSpacing(7)
        back_btn = QPushButton("← Classes")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(back_btn)

        self._breed_icon = QLabel()
        self._breed_icon.setFixedSize(28, 28)
        self._breed_icon.setScaledContents(True)
        header.addWidget(self._breed_icon)

        self._breed_title = QLabel("Classe")
        self._breed_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        header.addWidget(self._breed_title, 1)

        self._grid_mode_btn = QPushButton("Grille")
        self._grid_mode_btn.setCheckable(True)
        self._grid_mode_btn.setChecked(True)
        self._grid_mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._grid_mode_btn.clicked.connect(lambda: self._set_view_mode("grid"))
        header.addWidget(self._grid_mode_btn)

        self._list_mode_btn = QPushButton("Liste")
        self._list_mode_btn.setCheckable(True)
        self._list_mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._list_mode_btn.clicked.connect(lambda: self._set_view_mode("list"))
        header.addWidget(self._list_mode_btn)

        self._pin_btn = QPushButton("📌 Épingler")
        self._pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pin_btn.clicked.connect(self._on_pin_clicked)
        header.addWidget(self._pin_btn)
        root.addLayout(header)

        # Encadré mémo mécanique (repliable)
        self._tip_frame = QFrame()
        self._tip_frame.setObjectName("TipBanner")
        tip_layout = QVBoxLayout(self._tip_frame)
        tip_layout.setContentsMargins(9, 5, 9, 5)
        tip_layout.setSpacing(2)

        tip_head = QHBoxLayout()
        tip_lbl = QLabel("Mécanique clé")
        tip_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #bef264;")
        tip_head.addWidget(tip_lbl, 1)
        self._tip_toggle = QPushButton("Masquer")
        self._tip_toggle.setObjectName("TitleBtn")
        self._tip_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tip_toggle.clicked.connect(self._toggle_tip)
        tip_head.addWidget(self._tip_toggle)
        tip_layout.addLayout(tip_head)

        self._tip_body = QLabel("")
        self._tip_body.setWordWrap(True)
        self._tip_body.setStyleSheet("font-size: 11.5px; color: #ecfccb;")
        tip_layout.addWidget(self._tip_body)
        root.addWidget(self._tip_frame)

        # Barre de recherche + bouton Réinitialiser
        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Chercher sort ou effet (ex. proie, érosion, débuff, téléporte)...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._refresh_list)
        search_row.addWidget(self._search, 1)

        self._reset_btn = QPushButton("Tout voir")
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_btn.clicked.connect(self.reset_filters)
        search_row.addWidget(self._reset_btn)
        root.addLayout(search_row)

        # Filtres Éléments + Catégories avec FlowLayout (jamais coupés)
        elem_container = QWidget()
        elem_flow = FlowLayout(elem_container, margin=0, spacing=4)
        self._elem_buttons: dict[str, QPushButton] = {}
        for elem in ELEMENTS:
            btn = QPushButton(elem)
            btn.setObjectName("FilterPill")
            btn.setCheckable(True)
            btn.setChecked(elem == "Tous")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, e=elem: self._select_element(e))
            elem_flow.addWidget(btn)
            self._elem_buttons[elem] = btn
        root.addWidget(elem_container)

        tag_container = QWidget()
        tag_flow = FlowLayout(tag_container, margin=0, spacing=4)
        self._tag_buttons: dict[str, QPushButton] = {}
        for tag in QUICK_TAGS:
            btn = QPushButton(tag)
            btn.setObjectName("FilterPill")
            btn.setCheckable(True)
            btn.setChecked(tag == "Tous")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, t=tag: self._select_tag(t))
            tag_flow.addWidget(btn)
            self._tag_buttons[tag] = btn
        root.addWidget(tag_container)

        # Zone principale scrollable des sorts
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 2, 4, 2)
        self._list_layout.setSpacing(6)
        self._scroll.setWidget(self._list_container)
        root.addWidget(self._scroll, 1)

        # Panneau de détail en bas (actif en mode Grille)
        self._detail_drawer = QFrame()
        self._detail_drawer.setObjectName("DetailDrawer")
        d_layout = QVBoxLayout(self._detail_drawer)
        d_layout.setContentsMargins(10, 8, 10, 8)
        d_layout.setSpacing(4)

        d_top = QHBoxLayout()
        d_top.setSpacing(8)
        self._detail_icon = QLabel()
        self._detail_icon.setFixedSize(36, 36)
        self._detail_icon.setScaledContents(True)
        self._detail_icon.setStyleSheet("background: rgba(15, 23, 42, 180); border-radius: 5px;")
        d_top.addWidget(self._detail_icon)

        d_head_col = QVBoxLayout()
        d_head_col.setSpacing(1)
        self._detail_title = QLabel("Cliquez sur un sort pour voir sa description")
        self._detail_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        d_head_col.addWidget(self._detail_title)

        self._detail_stats = QLabel("")
        self._detail_stats.setStyleSheet("font-size: 11px; font-weight: 600; color: #bef264;")
        d_head_col.addWidget(self._detail_stats)
        d_top.addLayout(d_head_col, 1)
        d_layout.addLayout(d_top)

        self._detail_desc = QLabel("")
        self._detail_desc.setWordWrap(True)
        self._detail_desc.setStyleSheet("font-size: 11.5px; color: #e2e8f0;")
        d_layout.addWidget(self._detail_desc)
        root.addWidget(self._detail_drawer)

        self._icon_cache.icon_ready.connect(self._on_icon_ready)

    def set_breed(
        self,
        breed: BreedInfo,
        is_pinned: bool = False,
        initial_query: str = "",
        initial_tag: str = "Tous",
    ) -> None:
        self._breed = breed
        self._breed_title.setText(breed.name)
        self.set_pinned_state(is_pinned)

        if breed.img_url:
            pix = self._icon_cache.get_pixmap(breed.img_url)
            if pix is not None:
                self._breed_icon.setPixmap(pix)
            else:
                self._breed_icon.clear()
                self._icon_labels.setdefault(breed.img_url, []).append(self._breed_icon)

        if breed.tip:
            self._tip_frame.show()
            self._tip_body.setText(breed.tip)
            self._tip_body.show()
            self._tip_toggle.setText("Masquer")
        else:
            self._tip_frame.hide()

        self._search.blockSignals(True)
        self._search.setText(initial_query)
        self._search.blockSignals(False)
        self._select_element("Tous", refresh=False)
        self._select_tag(initial_tag if initial_tag in self._tag_buttons else "Tous", refresh=False)
        self._selected_spell = None
        self._refresh_list()
        self._scroll.verticalScrollBar().setValue(0)

    def reset_filters(self) -> None:
        self._search.blockSignals(True)
        self._search.clear()
        self._search.blockSignals(False)
        self._select_element("Tous", refresh=False)
        self._select_tag("Tous", refresh=False)
        self._refresh_list()

    def set_pinned_state(self, is_pinned: bool) -> None:
        self._pin_btn.setText("📌 Épinglée" if is_pinned else "📌 Épingler")

    def _set_view_mode(self, mode: str) -> None:
        self._view_mode = mode
        self._grid_mode_btn.setChecked(mode == "grid")
        self._list_mode_btn.setChecked(mode == "list")
        self._detail_drawer.setVisible(mode == "grid")
        self._refresh_list()

    def _on_pin_clicked(self) -> None:
        if self._breed is not None:
            self.pin_requested.emit(self._breed.id)

    def _toggle_tip(self) -> None:
        visible = self._tip_body.isVisible()
        self._tip_body.setVisible(not visible)
        self._tip_toggle.setText("Afficher" if visible else "Masquer")

    def _select_element(self, elem: str, refresh: bool = True) -> None:
        self._selected_element = elem
        for name, btn in self._elem_buttons.items():
            btn.setChecked(name == elem)
        if refresh:
            self._refresh_list()

    def _select_tag(self, tag: str, refresh: bool = True) -> None:
        self._selected_tag = tag
        for name, btn in self._tag_buttons.items():
            btn.setChecked(name == tag)
        if refresh:
            self._refresh_list()

    def _clear_list(self) -> None:
        self._icon_labels.clear()
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _refresh_list(self) -> None:
        self._clear_list()
        if self._breed is None:
            return

        query = self._search.text()
        has_filter = bool(query.strip()) or self._selected_element != "Tous" or self._selected_tag != "Tous"
        self._reset_btn.setVisible(has_filter)

        pairs = SpellRepository.filter_pairs(
            self._breed,
            query=query,
            element=self._selected_element,
            tag=self._selected_tag,
        )
        if not pairs:
            empty = QLabel("Aucun sort ne correspond aux filtres actuels.")
            empty.setObjectName("MutedLabel")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._list_layout.addWidget(empty)
            self._list_layout.addStretch(1)
            return

        # Pré-sélectionne un sort correspondant si aucun n'est encore affiché en détail
        visible_spells = [sp for pair in pairs for sp in pair.spells]
        if self._selected_spell not in visible_spells:
            matching = [
                sp
                for sp in visible_spells
                if SpellRepository.spell_matches(
                    sp, query=query, element=self._selected_element, tag=self._selected_tag
                )
            ]
            self._selected_spell = matching[0] if matching else visible_spells[0]
        self._render_detail_drawer(self._selected_spell)

        if self._view_mode == "grid":
            self._detail_drawer.show()
            grid_host = QWidget()
            grid = QGridLayout(grid_host)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(6)
            for idx, pair in enumerate(pairs):
                pair_widget = self._build_compact_pair(pair, query, has_filter)
                grid.addWidget(pair_widget, idx // 2, idx % 2)
            self._list_layout.addWidget(grid_host)
        else:
            self._detail_drawer.hide()
            for pair in pairs:
                self._list_layout.addWidget(self._build_pair_widget(pair))

        self._list_layout.addStretch(1)

    def _build_compact_pair(
        self,
        pair: SpellVariantPair,
        query: str,
        has_filter: bool,
    ) -> QFrame:
        frame = QFrame()
        frame.setObjectName("PairRow")
        row = QHBoxLayout(frame)
        row.setContentsMargins(4, 4, 4, 4)
        row.setSpacing(4)

        for idx, sp in enumerate(pair.spells):
            matched = SpellRepository.spell_matches(
                sp, query=query, element=self._selected_element, tag=self._selected_tag
            )
            pill = _ClickableSpellPill(
                spell=sp,
                is_variant=(idx == 1),
                dimmed=(has_filter and not matched),
                selected=(self._selected_spell is not None and sp.id == self._selected_spell.id),
                icon_cache=self._icon_cache,
                icon_registry=self._icon_labels,
            )
            pill.clicked.connect(self._on_spell_clicked)
            row.addWidget(pill, 1)
        return frame

    def _on_spell_clicked(self, spell: SpellInfo) -> None:
        self._selected_spell = spell
        self._refresh_list()

    def _render_detail_drawer(self, spell: SpellInfo | None) -> None:
        if spell is None:
            self._detail_title.setText("Cliquez sur un sort pour voir sa description")
            self._detail_stats.setText("")
            self._detail_desc.setText("")
            self._detail_icon.clear()
            return

        if spell.img_url:
            pix = self._icon_cache.get_pixmap(spell.img_url)
            if pix is not None:
                self._detail_icon.setPixmap(pix)
            else:
                self._detail_icon.clear()
                self._icon_labels.setdefault(spell.img_url, []).append(self._detail_icon)

        self._detail_title.setText(f"{spell.name}  ({spell.element})")
        stats = [f"{spell.ap_cost} PA", spell.format_range()]
        stats.append("LDV requise" if spell.requires_los else "Sans LDV")
        if spell.cast_in_line:
            stats.append("En ligne")
        if spell.cooldown > 0:
            stats.append(f"Relance {spell.cooldown}t")
        elif spell.max_per_turn > 0:
            stats.append(f"{spell.max_per_turn}/tour")
        if spell.tags:
            stats.append(" | ".join(spell.tags[:4]))
        self._detail_stats.setText("  •  ".join(stats))
        self._detail_desc.setText(spell.description or "Aucune description.")

    def _build_pair_widget(self, pair: SpellVariantPair) -> QFrame:
        frame = QFrame()
        frame.setObjectName("PairRow")
        row = QHBoxLayout(frame)
        row.setContentsMargins(6, 6, 6, 6)
        row.setSpacing(6)

        row.addWidget(self._build_spell_card(pair.primary, is_variant=False), 1)
        if pair.variant is not None:
            row.addWidget(self._build_spell_card(pair.variant, is_variant=True), 1)
        return frame

    def _build_spell_card(self, spell: SpellInfo, is_variant: bool) -> QFrame:
        card = QFrame()
        card.setObjectName("SpellCard")
        col = QVBoxLayout(card)
        col.setContentsMargins(8, 7, 8, 7)
        col.setSpacing(5)

        top = QHBoxLayout()
        top.setSpacing(7)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(34, 34)
        icon_lbl.setScaledContents(True)
        icon_lbl.setStyleSheet("background-color: rgba(15, 23, 42, 180); border-radius: 5px;")
        if spell.img_url:
            pix = self._icon_cache.get_pixmap(spell.img_url)
            if pix is not None:
                icon_lbl.setPixmap(pix)
            else:
                self._icon_labels.setdefault(spell.img_url, []).append(icon_lbl)
        top.addWidget(icon_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        role_txt = "VARIANTE" if is_variant else "SORT"
        color = ELEMENT_COLORS.get(spell.element, "#94a3b8")

        name_lbl = QLabel(spell.name)
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet("font-size: 12.5px; font-weight: 700; color: #f8fafc;")
        title_col.addWidget(name_lbl)

        meta_lbl = QLabel(f"{role_txt} • {spell.element}")
        meta_lbl.setStyleSheet(f"font-size: 10.5px; font-weight: 600; color: {color};")
        title_col.addWidget(meta_lbl)
        top.addLayout(title_col, 1)
        col.addLayout(top)

        badges = [f"{spell.ap_cost} PA", spell.format_range()]
        if not spell.requires_los:
            badges.append("Sans LDV")
        if spell.cast_in_line:
            badges.append("Ligne")
        if spell.cooldown > 0:
            badges.append(f"CD {spell.cooldown}")
        elif spell.max_per_turn > 0:
            badges.append(f"{spell.max_per_turn}/tour")

        stats_lbl = QLabel("  |  ".join(badges))
        stats_lbl.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #cbd5e1; "
            "background-color: rgba(15, 23, 42, 130); border-radius: 4px; padding: 3px 6px;"
        )
        col.addWidget(stats_lbl)

        if spell.tags:
            tags_lbl = QLabel(" • ".join(spell.tags[:4]))
            tags_lbl.setStyleSheet("font-size: 10.5px; color: #a3e635; font-weight: 600;")
            col.addWidget(tags_lbl)

        desc_lbl = QLabel(spell.description or "Aucune description.")
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 11px; color: #cbd5e1;")
        col.addWidget(desc_lbl)
        col.addStretch(1)
        return card

    def _on_icon_ready(self, url: str, pixmap: QPixmap) -> None:
        for lbl in self._icon_labels.get(url, []):
            if isValid(lbl):
                lbl.setPixmap(pixmap)
