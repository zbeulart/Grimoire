"""Tests du rendu des effets (infobulle façon Dofus) et de la génération de la page du grimoire."""

import json

from bworkgrimoire.effects import EffectCatalog, format_effect, spell_tooltip_data
from bworkgrimoire.models import BreedInfo, SpellInfo, SpellVariantPair
from bworkgrimoire.repository import SpellRepository
from bworkgrimoire.web_page import IconResolver, export_web_bundle, render_page


def _catalog() -> EffectCatalog:
    return EffectCatalog(
        spells={
            10: {"id": 10, "name": {"fr": "Mot Test"}, "spellLevels": [100, 101]},
            20: {"id": 20, "name": {"fr": "Sous-sort"}, "spellLevels": [200]},
        },
        levels={
            101: {
                "criticalHitProbability": 10,
                "maxStack": 2,
                "grade": 6,
                "effects": [
                    {"effectId": 96, "diceNum": 10, "diceSide": 12, "value": 0, "visibleInTooltip": True},
                    {"effectId": 950, "diceNum": 0, "diceSide": 0, "value": 7, "duration": 2, "visibleInTooltip": True},
                    {"effectId": 666, "visibleInTooltip": True},
                    {"effectId": 1160, "diceNum": 20, "visibleInTooltip": True},
                ],
                "criticalEffect": [
                    {"effectId": 96, "diceNum": 13, "diceSide": 15, "value": 0, "visibleInTooltip": True},
                ],
            },
            200: {
                "effects": [{"effectId": 108, "diceNum": 5, "diceSide": 0, "value": 0, "visibleInTooltip": True}],
            },
        },
        effects={
            96: {"description": {"fr": "#1{{~1~2 à }}#2 dommages Eau"}, "elementId": 3},
            108: {"description": {"fr": "#1{{~1~2 à }}#2 PV rendus"}, "elementId": 2, "characteristic": 0},
            950: {"description": {"fr": "État #3"}, "elementId": -1},
            666: {"description": {"fr": "Pas d'effet supplémentaire"}, "elementId": -1},
            1160: {"description": {"fr": "#1"}, "elementId": -1},
        },
        states={7: "Pesanteur"},
    )


def test_format_effect_damage_range_and_element():
    html, kind, element = format_effect({"effectId": 96, "diceNum": 10, "diceSide": 12}, _catalog())
    assert html == "<b>10</b> à <b>12</b> dommages Eau"
    assert (kind, element) == ("dmg", "eau")


def test_format_effect_state_with_duration():
    html, kind, _ = format_effect({"effectId": 950, "value": 7, "duration": 2}, _catalog())
    assert '<b class="nm">Pesanteur</b>' in html
    assert "– 2" in html
    assert kind == "state"


def test_tooltip_inlines_subspell_skips_noise_and_keeps_critical():
    data = spell_tooltip_data(10, _catalog())
    texts = [line[0] for line in data["fx"]]
    assert len(texts) == 3  # dommages, état, sous-sort ; l'effet 666 est ignoré
    assert texts[2].startswith("<b>5</b>")
    assert data["cfx"][0][0] == "<b>13</b> à <b>15</b> dommages Eau"
    assert (data["stack"], data["grade"]) == (2, 6)


def test_icon_resolver_prefers_local_file(tmp_path):
    (tmp_path / "sort_1.png").write_bytes(b"png")
    resolve = IconResolver([tmp_path])
    assert resolve("https://api.dofusdb.fr/img/sort_1.png").startswith("file:")
    assert resolve("https://api.dofusdb.fr/img/absent.png") == "https://api.dofusdb.fr/img/absent.png"
    assert resolve("") == ""

    rel_resolve = IconResolver([tmp_path], prefix="icons/")
    assert rel_resolve("https://api.dofusdb.fr/img/sort_1.png") == "icons/sort_1.png"


def test_render_page_injects_data_host_and_channel():
    template = "<!--QWEBCHANNEL--><style>{{WEB_BASE}}f.ttf</style><script>const DATA = /*DATA*/null;HOST=/*HOST*/'web'</script>"
    payload = {"breeds": [{"name": "Éniripsa", "pairs": []}]}
    qt = render_page(template, payload, "qt", "file:///web/")
    assert "qrc:///qtwebchannel/qwebchannel.js" in qt
    assert 'HOST="qt"' in qt and "file:///web/f.ttf" in qt
    assert json.dumps(payload, ensure_ascii=False, separators=(",", ":")) in qt
    web = render_page(template, payload, "web", "")
    assert "qwebchannel" not in web and 'HOST="web"' in web


def test_export_web_bundle_builds_portable_static_site(tmp_path):
    data_dir = tmp_path / "data"
    (data_dir / "web" / "fonts").mkdir(parents=True)
    (data_dir / "web" / "fonts" / "AlegreyaSans-Regular.ttf").write_bytes(b"ttf")
    (data_dir / "web" / "book_closed.svg").write_text("<svg/>", encoding="utf-8")
    (data_dir / "web" / "grimoire.html").write_text(
        '<link href="{{WEB_BASE}}book_closed.svg"><!--QWEBCHANNEL-->'
        '<style>{{WEB_BASE}}fonts/AlegreyaSans-Regular.ttf</style>'
        '<script>const DATA=/*DATA*/null;window.HOST=/*HOST*/\'web\';</script>',
        encoding="utf-8",
    )
    (data_dir / "icons").mkdir(parents=True)
    (data_dir / "icons" / "s1.png").write_bytes(b"png")
    (data_dir / "icons" / "s2.png").write_bytes(b"png")
    (data_dir / "icons" / "cls.png").write_bytes(b"png")

    s1 = SpellInfo.from_dict({"id": 1, "name": "Mot 1", "img_url": "https://ex/s1.png", "element": "Feu"})
    s2 = SpellInfo.from_dict({"id": 2, "name": "Mot 2", "img_url": "https://ex/s2.png", "element": "Eau"})
    pair = SpellVariantPair(variant_id=1, primary=s1, variant=s2)
    repo = SpellRepository([BreedInfo(10, "Éniripsa", "", "https://ex/cls.png", (pair,))])

    out_dir = tmp_path / "web_dist"
    index_path = export_web_bundle(repo, out_dir, data_dir=data_dir)
    html = index_path.read_text(encoding="utf-8")

    assert index_path == out_dir / "index.html"
    assert (out_dir / "fonts" / "AlegreyaSans-Regular.ttf").exists()
    assert (out_dir / "icons" / "s1.png").exists()
    assert (out_dir / "book_closed.svg").exists()
    assert 'HOST="web"' in html
    assert "qwebchannel" not in html
    assert "file://" not in html
    assert "icons/s1.png" in html
    assert '"fonts/AlegreyaSans-Regular.ttf"' in html or 'fonts/AlegreyaSans-Regular.ttf' in html
