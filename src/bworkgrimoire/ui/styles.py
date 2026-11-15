"""Feuille de style sombre compacte adaptée à un overlay par-dessus Dofus."""

ELEMENT_COLORS: dict[str, str] = {
    "Feu": "#ef4444",
    "Eau": "#38bdf8",
    "Air": "#4ade80",
    "Terre": "#f59e0b",
    "Neutre": "#a1a1aa",
    "Multi": "#c084fc",
    "Utilitaire": "#94a3b8",
}

OVERLAY_QSS = """
QWidget#RootCard {
    background-color: rgba(18, 20, 28, 244);
    border: 1px solid rgba(132, 204, 22, 115);
    border-radius: 12px;
    color: #f1f5f9;
    font-family: "Segoe UI", sans-serif;
}

QWidget#TitleBar {
    background-color: rgba(26, 29, 40, 248);
    border-top-left-radius: 11px;
    border-top-right-radius: 11px;
    border-bottom: 1px solid rgba(255, 255, 255, 18);
}

QLabel {
    color: #f1f5f9;
}

QLabel#MutedLabel {
    color: #94a3b8;
    font-size: 11px;
}

QLineEdit {
    background-color: rgba(30, 34, 48, 240);
    border: 1px solid rgba(148, 163, 184, 70);
    border-radius: 7px;
    padding: 6px 10px;
    color: #f8fafc;
    font-size: 12px;
}

QLineEdit:focus {
    border: 1px solid #84cc16;
}

QPushButton {
    background-color: rgba(38, 43, 60, 230);
    border: 1px solid rgba(148, 163, 184, 55);
    border-radius: 6px;
    padding: 4px 9px;
    color: #e2e8f0;
    font-size: 12px;
}

QPushButton:hover {
    background-color: rgba(54, 61, 84, 245);
    border-color: rgba(132, 204, 22, 140);
}

QPushButton:checked {
    background-color: rgba(132, 204, 22, 60);
    border-color: #84cc16;
    color: #ecfccb;
    font-weight: 600;
}

QPushButton#FilterPill {
    background-color: rgba(30, 34, 48, 215);
    border: 1px solid rgba(148, 163, 184, 50);
    border-radius: 11px;
    padding: 3px 9px;
    color: #cbd5e1;
    font-size: 11px;
}

QPushButton#FilterPill:hover {
    border-color: rgba(132, 204, 22, 150);
    color: #f8fafc;
}

QPushButton#FilterPill:checked {
    background-color: rgba(132, 204, 22, 65);
    border-color: #84cc16;
    color: #ecfccb;
    font-weight: 700;
}

QPushButton#TitleBtn {
    background-color: transparent;
    border: none;
    padding: 3px 7px;
    border-radius: 5px;
    font-weight: 600;
}

QPushButton#TitleBtn:hover {
    background-color: rgba(255, 255, 255, 24);
}

QToolButton#ClassTile {
    background-color: rgba(28, 32, 45, 225);
    border: 1px solid rgba(148, 163, 184, 48);
    border-radius: 8px;
    padding: 6px 4px;
    color: #f1f5f9;
    font-size: 12px;
    font-weight: 600;
}

QToolButton#ClassTile:hover {
    background-color: rgba(44, 52, 72, 245);
    border: 1px solid #84cc16;
}

QFrame#TipBanner {
    background-color: rgba(132, 204, 22, 22);
    border: 1px solid rgba(132, 204, 22, 80);
    border-radius: 8px;
}

QFrame#PairRow {
    background-color: rgba(24, 27, 38, 225);
    border: 1px solid rgba(148, 163, 184, 38);
    border-radius: 9px;
}

QFrame#SpellCard {
    background-color: rgba(31, 35, 50, 215);
    border: 1px solid rgba(148, 163, 184, 35);
    border-radius: 7px;
}

QFrame#DetailDrawer {
    background-color: rgba(23, 27, 38, 245);
    border: 1px solid rgba(132, 204, 22, 95);
    border-radius: 9px;
}

QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background: transparent;
    width: 7px;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background: rgba(148, 163, 184, 85);
    border-radius: 3px;
    min-height: 24px;
}
"""
