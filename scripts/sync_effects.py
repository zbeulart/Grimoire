"""Synchronise les effets exacts des sorts (infobulle façon Dofus) depuis api.dofusdb.fr.

À lancer après ``sync_dofusdb.py`` : lit data/spells_fr.json et écrit data/spell_effects_fr.json.

Usage :
    python scripts/sync_effects.py

Attribution : Données extraites de DofusDB (https://dofusdb.fr) — licence non-commerciale.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bworkgrimoire.effects import EffectCatalog, spell_tooltip_data  # noqa: E402

BASE_URL = "https://api.dofusdb.fr"
HEADERS = {"User-Agent": "BworkGrimoire/0.1 (+https://bworkshop.app)"}
CHUNK = 50
MAX_DEPTH = 4  # profondeur de sous-sorts suivis (sort -> sous-sort -> ...)


def fetch_by_ids(client: httpx.Client, endpoint: str, ids: set[int]) -> dict[int, dict]:
    """Récupère des objets DofusDB par paquets d'IDs."""
    result: dict[int, dict] = {}
    ordered = sorted(i for i in ids if i)
    for start in range(0, len(ordered), CHUNK):
        chunk = ordered[start : start + CHUNK]
        params = [("$limit", str(CHUNK))] + [("id[$in][]", str(i)) for i in chunk]
        resp = client.get(f"{BASE_URL}/{endpoint}", params=params)
        resp.raise_for_status()
        for entry in resp.json().get("data", []):
            result[int(entry["id"])] = entry
    return result


def all_effects(level: dict) -> list[dict]:
    return list(level.get("effects", [])) + list(level.get("criticalEffect", []))


def _pick_name(obj: dict, lang: str) -> str:
    names = obj.get("name") or {}
    return names.get(lang) or names.get("fr") or names.get("en") or ""


def build_catalog(client: httpx.Client, spell_ids: set[int]) -> tuple[EffectCatalog, dict[int, dict], dict[int, dict]]:
    catalog = EffectCatalog()
    todo = set(spell_ids)
    for depth in range(MAX_DEPTH):
        new_spells = fetch_by_ids(client, "spells", todo - set(catalog.spells))
        catalog.spells.update(new_spells)
        level_ids = {int(max(s["spellLevels"])) for s in new_spells.values() if s.get("spellLevels")}
        new_levels = fetch_by_ids(client, "spell-levels", level_ids)
        catalog.levels.update(new_levels)

        effect_ids = {int(e["effectId"]) for lv in new_levels.values() for e in all_effects(lv)}
        catalog.effects.update(fetch_by_ids(client, "effects", effect_ids - set(catalog.effects)))

        # Sous-sorts : effets dont le modèle est « #1 » (lance le sort diceNum)
        todo = {
            int(e["diceNum"])
            for lv in new_levels.values()
            for e in all_effects(lv)
            if catalog.template(e["effectId"]).strip() == "#1" and e.get("diceNum")
        } - set(catalog.spells)
        print(f"    profondeur {depth + 1} : {len(catalog.spells)} sorts, {len(catalog.effects)} effets")
        if not todo:
            break

    state_ids: set[int] = set()
    monster_ids: set[int] = set()
    for lv in catalog.levels.values():
        for e in all_effects(lv):
            if int(e["effectId"]) in (950, 951, 952):
                state_ids.add(int(e["value"]))
            if int(e["effectId"]) in (181, 1008, 1011, 405, 2796, 1097):
                monster_ids.add(int(e["diceNum"]))
    raw_states = fetch_by_ids(client, "spell-states", state_ids)
    raw_monsters = fetch_by_ids(client, "monsters", monster_ids)
    catalog.states = {i: _pick_name(o, "fr") for i, o in raw_states.items()}
    catalog.monsters = {i: _pick_name(o, "fr") for i, o in raw_monsters.items()}
    return catalog, raw_states, raw_monsters


def build_payload(
    catalog: EffectCatalog,
    raw_states: dict[int, dict],
    raw_monsters: dict[int, dict],
    spell_ids: set[int],
    lang: str,
) -> dict:
    catalog.states = {i: _pick_name(o, lang) for i, o in raw_states.items()}
    catalog.monsters = {i: _pick_name(o, lang) for i, o in raw_monsters.items()}
    return {
        "source": "DofusDB (https://dofusdb.fr)",
        "lang": lang,
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "spells": {str(sid): spell_tooltip_data(sid, catalog, lang=lang) for sid in sorted(spell_ids)},
    }


def main() -> None:
    spells_path = ROOT / "data" / "spells_fr.json"
    dataset = json.loads(spells_path.read_text(encoding="utf-8"))
    spell_ids = {
        int(sp["id"])
        for breed in dataset["breeds"]
        for pair in breed["pairs"]
        for sp in (pair.get("primary"), pair.get("variant"))
        if sp
    }
    print(f"Récupération des effets de {len(spell_ids)} sorts...")
    with httpx.Client(timeout=30.0, headers=HEADERS, follow_redirects=True) as client:
        catalog, raw_states, raw_monsters = build_catalog(client, spell_ids)

    for lang in ("fr", "en"):
        payload = build_payload(catalog, raw_states, raw_monsters, spell_ids, lang)
        out_path = ROOT / "data" / f"spell_effects_{lang}.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"Sauvegardé : {out_path}")


if __name__ == "__main__":
    main()
