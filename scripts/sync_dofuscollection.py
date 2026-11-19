"""Complète Grimoire avec les classes que DofusDB ne publie pas encore (ex. Bellaphone).

À lancer après ``sync_dofusdb.py`` et ``sync_effects.py`` : lit les données de sorts
publiées par DofusCollection (mêmes identifiants que le jeu) et ajoute, dans
data/spells_<lang>.json et data/spell_effects_<lang>.json, chaque classe absente
des fichiers DofusDB. Une classe que DofusDB publie déjà n'est jamais écrasée :
le jour où DofusDB ajoute le Bellaphone, ce script ne fait plus rien pour lui.

Les effets sont rendus avec les mêmes modèles d'effets DofusDB que les autres classes.

Usage :
    python scripts/sync_dofuscollection.py
    python scripts/sync_dofuscollection.py --with-icons   # télécharge aussi les PNG dans data/icons/

Attribution : sorts du Bellaphone extraits de DofusCollection (https://www.dofuscollection.com).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from bworkgrimoire.effects import EffectCatalog, spell_tooltip_data  # noqa: E402
from bworkgrimoire.models import (  # noqa: E402
    BreedInfo,
    SpellInfo,
    SpellVariantPair,
    clean_description,
    infer_element,
    infer_tactical_tags,
)
from sync_effects import fetch_by_ids  # noqa: E402

SITE = "https://www.dofuscollection.com"
SOURCE_URL = f"{SITE}/data/spells.json"
HEADERS = {"User-Agent": "BworkGrimoire/0.1 (+https://bworkshop.app)"}
LANGS = ("fr", "en")
STATE_EFFECTS = {950, 951, 952}
SUMMON_EFFECTS = {181, 1008, 1011, 405, 2796, 1097}
# Invocations sans nom ni chez DofusDB ni chez DofusCollection : nom repris de la description du sort.
KNOWN_SUMMONS = {8434: {"fr": "Pilier", "en": "Pillar"}}  # Piliers de la Terre (Bellaphone)


def spell_icon_url(icon_id: int) -> str:
    return f"{SITE}/img/spells/{icon_id}.png"


def breed_icon_url(breed_id: int) -> str:
    return f"{SITE}/img/breeds/symbol_{breed_id}.png"


def top_level(raw_spell: dict) -> tuple[dict, int]:
    """Niveau le plus haut du sort et son rang (1 = premier niveau)."""
    levels = sorted(raw_spell.get("levels", []), key=lambda lv: int(lv.get("lvl", 0)))
    if not levels:
        return {}, 0
    return levels[-1], len(levels)


def _text(raw: dict, key_fr: str, key_en: str, lang: str) -> str:
    if lang == "en":
        return raw.get(key_en) or raw.get(key_fr) or ""
    return raw.get(key_fr) or ""


def build_spell(raw_spell: dict, lang: str) -> SpellInfo:
    """Convertit un sort DofusCollection en SpellInfo (mêmes champs que DofusDB)."""
    level, _ = top_level(raw_spell)
    fr_name = raw_spell.get("n", "")
    fr_description = clean_description(raw_spell.get("d", ""))
    return SpellInfo(
        id=int(raw_spell["i"]),
        name=_text(raw_spell, "n", "ne", lang),
        description=clean_description(_text(raw_spell, "d", "de", lang)),
        img_url=spell_icon_url(int(raw_spell["ic"])) if raw_spell.get("ic") else "",
        ap_cost=int(level.get("ap", 0)),
        min_range=int(level.get("minR", 0)),
        max_range=int(level.get("maxR", 0)),
        range_modifiable=bool(level.get("boost", False)),
        cast_in_line=bool(level.get("line", False)),
        cast_in_diagonal=False,
        requires_los=bool(level.get("los", False)),
        cooldown=int(level.get("cd", 0)),
        max_per_turn=int(level.get("mpt", 0)),
        max_per_target=int(level.get("mptp", 0)),
        crit_chance=int(level.get("crit", 0)),
        element=infer_element(fr_description),
        tags=infer_tactical_tags(fr_name, fr_description),
    )


def build_auras(extra_spells: list[dict], lang: str) -> tuple[SpellVariantPair, ...]:
    """Sorts propres à la classe hors variantes, rangés par deux comme sur DofusCollection.

    Pour le Bellaphone : chaque Bellaura suivie de son sort de lignée
    (Bellaura Ébène -> Royaume des Ombres, Bellaura Ivoire -> Tour d'Ivoire, ...).
    """
    auras = []
    for idx in range(0, len(extra_spells) - 1, 2):
        aura, lineage = extra_spells[idx], extra_spells[idx + 1]
        auras.append(
            SpellVariantPair(variant_id=0, primary=build_spell(aura, lang), variant=build_spell(lineage, lang))
        )
    return tuple(auras)


def build_breed(breed_id: int, raw_breed: dict, lang: str, extra_spells: list[dict] | None = None) -> dict:
    pairs = []
    for var in raw_breed.get("variants", []):
        spells = var.get("s", [])
        if not spells:
            continue
        pairs.append(
            SpellVariantPair(
                variant_id=int(var.get("vi", 0)),
                primary=build_spell(spells[0], lang),
                variant=build_spell(spells[1], lang) if len(spells) > 1 else None,
            )
        )
    return BreedInfo(
        id=breed_id,
        name=raw_breed.get("n", ""),
        description="",
        img_url=breed_icon_url(breed_id),
        pairs=tuple(pairs),
        auras=build_auras(extra_spells or [], lang),
    ).to_dict()


def to_dofusdb_effect(effect: dict) -> dict:
    """Effet DofusCollection -> forme « spell-levels » de DofusDB attendue par effects.py."""
    # Effets sans dés (ex. « Soin sur l'attaquant : #1% ») : la valeur n'est que dans « v ».
    dice_num = effect.get("dn")
    if dice_num is None:
        dice_num = effect.get("v", 0)
    return {
        "effectId": int(effect["eid"]),
        "diceNum": int(dice_num or 0),
        "diceSide": int(effect.get("ds", 0)),
        "value": int(effect.get("v", 0)),
        "duration": int(effect.get("dur", 0)),
        "visibleInTooltip": bool(effect.get("vtt", False)),
    }


def add_spell_to_catalog(catalog: EffectCatalog, raw_spell: dict) -> None:
    level, grade = top_level(raw_spell)
    if not level:
        return
    spell_id, level_id = int(raw_spell["i"]), int(level["i"])
    catalog.spells[spell_id] = {
        "id": spell_id,
        "name": {"fr": raw_spell.get("n", ""), "en": raw_spell.get("ne") or raw_spell.get("n", "")},
        "spellLevels": [level_id],
    }
    catalog.levels[level_id] = {
        "id": level_id,
        "grade": grade,
        "criticalHitProbability": int(level.get("crit", 0)),
        "maxStack": int(level.get("ms", 0)),
        "effects": [to_dofusdb_effect(e) for e in level.get("ef", [])],
        "criticalEffect": [to_dofusdb_effect(e) for e in level.get("cef", [])],
    }


def build_catalog(client: httpx.Client, source: dict, raw_spells: list[dict]) -> tuple[EffectCatalog, dict, dict]:
    """Catalogue d'effets : sorts DofusCollection + modèles d'effets, états, invocations."""
    catalog = EffectCatalog()
    for raw in raw_spells:
        add_spell_to_catalog(catalog, raw)
    # Sorts liés (sous-sorts, sorts cités par nom dans les effets) quand la source les fournit.
    for group in ("linkedSpells", "triggerSpells"):
        for sid, raw in (source.get(group) or {}).items():
            if int(sid) not in catalog.spells and raw.get("levels"):
                add_spell_to_catalog(catalog, {**raw, "i": int(sid)})

    effects = [e for lv in catalog.levels.values() for e in lv["effects"] + lv["criticalEffect"]]
    catalog.effects.update(fetch_by_ids(client, "effects", {e["effectId"] for e in effects}))

    states: dict[int, dict] = {int(k): v for k, v in (source.get("states") or {}).items()}
    monsters: dict[int, dict] = dict(KNOWN_SUMMONS)
    monsters.update(
        {
            int(k): {"fr": v.get("n", ""), "en": v.get("ne") or v.get("n", "")}
            for k, v in (source.get("summons") or {}).items()
        }
    )
    missing_states = {e["value"] for e in effects if e["effectId"] in STATE_EFFECTS} - set(states)
    missing_monsters = {e["diceNum"] for e in effects if e["effectId"] in SUMMON_EFFECTS} - set(monsters)
    for sid, raw in fetch_by_ids(client, "spell-states", missing_states).items():
        states[sid] = raw.get("name") or {}
    for mid, raw in fetch_by_ids(client, "monsters", missing_monsters).items():
        monsters[mid] = raw.get("name") or {}
    return catalog, states, monsters


def _pick(names: dict, lang: str) -> str:
    return names.get(lang) or names.get("fr") or names.get("en") or ""


def download_icons(urls: set[str], icons_dir: Path, client: httpx.Client) -> int:
    icons_dir.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    for url in sorted(urls):
        target = icons_dir / url.rsplit("/", 1)[-1]
        if target.exists():
            continue
        try:
            resp = client.get(url, timeout=10.0)
        except httpx.HTTPError:
            continue
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image/"):
            target.write_bytes(resp.content)
            downloaded += 1
    return downloaded


def missing_breeds(source: dict, known_ids: set[int]) -> dict[int, dict]:
    """Classes présentes chez DofusCollection mais absentes des fichiers DofusDB."""
    return {
        int(bid): raw
        for bid, raw in (source.get("breeds") or {}).items()
        if int(bid) not in known_ids and raw.get("variants")
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ajoute les classes absentes de DofusDB depuis DofusCollection.")
    parser.add_argument("--with-icons", action="store_true", help="Télécharge aussi les icônes PNG.")
    parser.add_argument("--source", default=SOURCE_URL, help="URL ou fichier local de spells.json.")
    args = parser.parse_args()

    data_dir = ROOT / "data"
    spells_files = {lang: data_dir / f"spells_{lang}.json" for lang in LANGS}
    effects_files = {lang: data_dir / f"spell_effects_{lang}.json" for lang in LANGS}
    datasets = {lang: json.loads(p.read_text(encoding="utf-8")) for lang, p in spells_files.items()}
    known = {int(b["id"]) for b in datasets["fr"]["breeds"]}

    with httpx.Client(timeout=30.0, headers=HEADERS, follow_redirects=True) as client:
        if Path(args.source).exists():
            source = json.loads(Path(args.source).read_text(encoding="utf-8"))
        else:
            resp = client.get(args.source)
            resp.raise_for_status()
            source = resp.json()

        todo = missing_breeds(source, known)
        if not todo:
            print("Aucune classe manquante : toutes les classes sont déjà dans data/.")
            return
        extra = source.get("breedExtraSpells") or {}
        raw_spells = [
            sp
            for bid, raw in todo.items()
            for sp in [s for v in raw["variants"] for s in v.get("s", [])] + extra.get(str(bid), [])
        ]
        print(f"Classes ajoutées depuis DofusCollection : {', '.join(r['n'] for r in todo.values())}")

        catalog, states, monsters = build_catalog(client, source, raw_spells)
        shown_ids = {int(s["i"]) for s in raw_spells}

        for lang in LANGS:
            dataset = datasets[lang]
            dataset["breeds"] = sorted(
                dataset["breeds"]
                + [build_breed(bid, raw, lang, extra.get(str(bid), [])) for bid, raw in todo.items()],
                key=lambda b: int(b["id"]),
            )
            dataset["source"] = "DofusDB (https://dofusdb.fr) + DofusCollection (https://www.dofuscollection.com)"
            spells_files[lang].write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")

            catalog.states = {i: _pick(n, lang) for i, n in states.items()}
            catalog.monsters = {i: _pick(n, lang) for i, n in monsters.items()}
            payload = json.loads(effects_files[lang].read_text(encoding="utf-8"))
            for sid in sorted(shown_ids):
                payload["spells"][str(sid)] = spell_tooltip_data(sid, catalog, lang=lang)
            effects_files[lang].write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
            )
            print(f"Sauvegardé : {spells_files[lang].name}, {effects_files[lang].name}")

        if args.with_icons:
            urls = {breed_icon_url(bid) for bid in todo} | {
                spell_icon_url(int(s["ic"])) for s in raw_spells if s.get("ic")
            }
            print(f"Icônes téléchargées : {download_icons(urls, data_dir / 'icons', client)}")


if __name__ == "__main__":
    main()
