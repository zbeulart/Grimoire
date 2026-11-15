"""Test de fumée PySide6 : ouverture grille, clic classe, épinglage et filtres."""

from pathlib import Path

from PySide6.QtWidgets import QApplication

from bworkgrimoire.icon_cache import IconCache
from bworkgrimoire.models import BreedInfo, SpellInfo, SpellVariantPair
from bworkgrimoire.repository import SpellRepository, default_data_dir
from bworkgrimoire.ui.main_window import OverlayWindow


def _get_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_overlay_navigation_and_pinning(tmp_path: Path) -> None:
    _get_app()
    ougi = BreedInfo(
        id=18,
        name="Ouginak",
        description="",
        img_url="",
        tip="Rage et Proie",
        pairs=(
            SpellVariantPair(
                variant_id=1,
                primary=SpellInfo(
                    id=101,
                    name="Tibia",
                    description="Occasionne des dommages Eau.",
                    img_url="",
                    ap_cost=3,
                    min_range=1,
                    max_range=4,
                    element="Eau",
                ),
                variant=SpellInfo(
                    id=102,
                    name="Cubitus",
                    description="Occasionne des dommages Air et repousse.",
                    img_url="",
                    ap_cost=3,
                    min_range=1,
                    max_range=3,
                    element="Air",
                    tags=("Placement",),
                ),
            ),
        ),
    )
    repo = SpellRepository([ougi])
    cache = IconCache(cache_dir=tmp_path)
    window = OverlayWindow(repo, icon_cache=cache, enable_tray=False)

    assert window._stack.currentIndex() == 0
    window.open_breed(18)
    assert window._stack.currentIndex() == 1
    assert window._spell_view._breed_title.text() == "Ouginak"

    window.toggle_pin_breed(18)
    assert 18 in window._pinned_breed_ids
    window.show_home()
    assert window._stack.currentIndex() == 0
    window.close()


def test_real_dataset_loads_all_19_classes_and_ouginak(tmp_path: Path) -> None:
    _get_app()
    spells_path = default_data_dir() / "spells_fr.json"
    if not spells_path.exists():
        return
    repo = SpellRepository.load_from_files()
    assert len(repo.breeds) == 19
    ougi = repo.get_breed(18)
    assert ougi is not None
    assert ougi.name == "Ouginak"
    assert any(p.primary.ap_cost > 0 for p in ougi.pairs)

    cache = IconCache(cache_dir=tmp_path)
    window = OverlayWindow(repo, icon_cache=cache, enable_tray=False)
    window._class_grid._select_tag("Pesanteur")
    assert "classe(s) trouvée(s)" in window._class_grid._status_lbl.text()

    window.open_breed(18, initial_tag="Pesanteur")
    assert window._spell_view._breed_title.text() == "Ouginak"
    assert window._spell_view._selected_tag == "Pesanteur"
    window._spell_view._set_view_mode("list")
    assert window._spell_view._view_mode == "list"
    window.close()
