"""Tests du complément DofusCollection (classes absentes de DofusDB) avec données mockées."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import sync_dofuscollection as sync  # noqa: E402
from bworkgrimoire.effects import EffectCatalog, spell_tooltip_data  # noqa: E402

RAW_SPELL = {
    "i": 33203,
    "n": "Réminiscence",
    "ne": "Reminiscence",
    "d": "Téléporte la cible à sa position précédente et occasionne des dommages Terre aux ennemis.",
    "de": "Teleports the target to its previous position and inflicts Earth damage on enemies.",
    "ic": 15665,
    "levels": [
        {"i": 87029, "ap": 3, "minR": 0, "maxR": 4, "crit": 10, "mpt": 3, "mptp": 2, "lvl": 1, "los": True, "ms": 1},
        {
            "i": 87915,
            "ap": 3,
            "minR": 0,
            "maxR": 6,
            "crit": 10,
            "mpt": 3,
            "mptp": 2,
            "cd": 0,
            "lvl": 136,
            "los": True,
            "boost": True,
            "ms": 1,
            "ef": [{"eid": 97, "dn": 24, "ds": 27, "elem": 1, "vtt": True}],
            "cef": [{"eid": 97, "dn": 29, "ds": 32, "elem": 1, "vtt": True}],
        },
    ],
}
RAW_BREED = {"n": "Bellaphone", "variants": [{"vi": 715, "s": [RAW_SPELL, {**RAW_SPELL, "i": 33204, "n": "Barkhane"}]}]}


def test_build_breed_uses_highest_level_and_both_languages() -> None:
    fr = sync.build_breed(21, RAW_BREED, "fr")
    en = sync.build_breed(21, RAW_BREED, "en")
    spell = fr["pairs"][0]["primary"]
    assert fr["id"] == 21 and fr["name"] == "Bellaphone"
    assert fr["img_url"].endswith("/img/breeds/symbol_21.png")
    assert fr["pairs"][0]["variant_id"] == 715
    assert fr["pairs"][0]["variant"]["name"] == "Barkhane"
    assert (spell["ap_cost"], spell["min_range"], spell["max_range"]) == (3, 0, 6)
    assert spell["range_modifiable"] is True and spell["requires_los"] is True
    assert (spell["max_per_turn"], spell["max_per_target"], spell["crit_chance"]) == (3, 2, 10)
    assert spell["element"] == "Terre"
    assert spell["img_url"].endswith("/img/spells/15665.png")
    assert en["pairs"][0]["primary"]["name"] == "Reminiscence"
    assert en["pairs"][0]["primary"]["element"] == "Terre"  # élément déduit du texte FR


def test_tooltip_rendered_with_dofusdb_templates() -> None:
    catalog = EffectCatalog(effects={97: {"id": 97, "elementId": 1, "description": {"fr": "#1{{~1~2 à }}#2 dommages Terre"}}})
    sync.add_spell_to_catalog(catalog, RAW_SPELL)
    data = spell_tooltip_data(33203, catalog)
    assert data["fx"] == [["<b>24</b> à <b>27</b> dommages Terre", "dmg", "terre"]]
    assert data["cfx"] == [["<b>29</b> à <b>32</b> dommages Terre", "dmg", "terre"]]
    assert (data["stack"], data["grade"]) == (1, 2)


def test_missing_breeds_never_overrides_dofusdb() -> None:
    source = {"breeds": {"8": {"n": "Iop", "variants": [{}]}, "21": RAW_BREED, "22": {"n": "Vide", "variants": []}}}
    assert list(sync.missing_breeds(source, known_ids={8})) == [21]
    assert sync.missing_breeds(source, known_ids={8, 21}) == {}


def test_auras_paired_with_lineage_spell_and_kept_in_payload() -> None:
    from bworkgrimoire.models import BreedInfo
    from bworkgrimoire.repository import SpellRepository
    from bworkgrimoire.web_page import IconResolver, build_payload

    aura = {**RAW_SPELL, "i": 33270, "n": "Bellaura Ébène", "ne": "Ebony Bellaura", "d": "Augmente la Fuite."}
    lineage = {**RAW_SPELL, "i": 33233, "n": "Royaume des Ombres", "ne": "Shadow Realm"}
    fr = sync.build_breed(21, RAW_BREED, "fr", [aura, lineage])
    en = sync.build_breed(21, RAW_BREED, "en", [aura, lineage])
    assert [(a["primary"]["name"], a["variant"]["name"]) for a in fr["auras"]] == [("Bellaura Ébène", "Royaume des Ombres")]

    breed = BreedInfo.from_dict(fr)
    assert BreedInfo.from_dict(breed.to_dict()).auras == breed.auras
    payload = build_payload(SpellRepository([breed]), {}, IconResolver([]), en_repo=SpellRepository([BreedInfo.from_dict(en)]))
    entry = payload["breeds"][0]
    assert entry["auras"][0]["a"]["name"] == "Bellaura Ébène"
    assert entry["auras"][0]["b"]["en"]["name"] == "Shadow Realm"


def test_effect_without_dice_takes_its_value() -> None:
    effect = sync.to_dofusdb_effect({"eid": 786, "v": 10, "vtt": True})
    assert effect["diceNum"] == 10
    assert sync.to_dofusdb_effect({"eid": 97, "dn": 24, "ds": 27, "v": 3})["diceNum"] == 24
