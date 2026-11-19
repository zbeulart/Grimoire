"""Synchronise les classes et tous leurs sorts/variantes depuis api.dofusdb.fr.

Usage :
    python scripts/sync_dofusdb.py
    python scripts/sync_dofusdb.py --with-icons   # pré-télécharge aussi les PNG dans data/icons/

Attribution : Données extraites de DofusDB (https://dofusdb.fr) — licence non-commerciale.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bworkgrimoire.models import (  # noqa: E402
    BreedInfo,
    SpellInfo,
    SpellVariantPair,
    clean_description,
    infer_element,
    infer_tactical_tags,
)

BASE_URL = "https://api.dofusdb.fr"
HEADERS = {"User-Agent": "BworkGrimoire/0.1 (+https://bworkshop.app)"}


def _pick(mapping: dict | str | None, lang: str = "fr") -> str:
    if isinstance(mapping, str):
        return mapping
    if not isinstance(mapping, dict):
        return ""
    return mapping.get(lang) or mapping.get("fr") or mapping.get("en") or ""


def fetch_breeds(client: httpx.Client) -> list[dict]:
    resp = client.get(f"{BASE_URL}/breeds", params={"$limit": 50, "lang": "fr"})
    resp.raise_for_status()
    return resp.json().get("data", [])


def fetch_all_variants(client: httpx.Client) -> list[dict]:
    items: list[dict] = []
    skip = 0
    limit = 50
    while True:
        resp = client.get(
            f"{BASE_URL}/spell-variants",
            params={"$limit": limit, "$skip": skip, "lang": "fr"},
        )
        resp.raise_for_status()
        payload = resp.json()
        batch = payload.get("data", [])
        items.extend(batch)
        total = payload.get("total", len(items))
        if not batch or len(items) >= total:
            break
        skip += limit
    return items


def fetch_spell_levels(client: httpx.Client, level_ids: list[int]) -> dict[int, dict]:
    """Récupère les caractéristiques des sorts par paquets de 50 IDs."""
    levels_by_id: dict[int, dict] = {}
    unique_ids = sorted(set(level_ids))
    chunk_size = 50
    for idx in range(0, len(unique_ids), chunk_size):
        chunk = unique_ids[idx : idx + chunk_size]
        params = [("$limit", str(len(chunk)))] + [("id[$in][]", str(lid)) for lid in chunk]
        resp = client.get(f"{BASE_URL}/spell-levels", params=params)
        resp.raise_for_status()
        for entry in resp.json().get("data", []):
            levels_by_id[int(entry["id"])] = entry
    return levels_by_id


def build_spell(raw_spell: dict, levels_by_id: dict[int, dict], lang: str = "fr") -> SpellInfo:
    """Construit un SpellInfo en choisissant le niveau maximal disponible."""
    level_ids = [int(lid) for lid in raw_spell.get("spellLevels", [])]
    candidates = [levels_by_id[lid] for lid in level_ids if lid in levels_by_id]
    best = max(candidates, key=lambda lv: lv.get("grade", 0), default={})

    fr_name = _pick(raw_spell.get("name"), "fr")
    fr_description = clean_description(_pick(raw_spell.get("description"), "fr"))
    name = _pick(raw_spell.get("name"), lang)
    description = clean_description(_pick(raw_spell.get("description"), lang))
    return SpellInfo(
        id=int(raw_spell["id"]),
        name=name,
        description=description,
        img_url=raw_spell.get("img", ""),
        ap_cost=int(best.get("apCost", 0)),
        min_range=int(best.get("minRange", 0)),
        max_range=int(best.get("range", 0)),
        range_modifiable=bool(best.get("rangeCanBeBoosted", False)),
        cast_in_line=bool(best.get("castInLine", False)),
        cast_in_diagonal=bool(best.get("castInDiagonal", False)),
        requires_los=bool(best.get("castTestLos", True)),
        cooldown=int(best.get("minCastInterval", 0)),
        max_per_turn=int(best.get("maxCastPerTurn", 0)),
        max_per_target=int(best.get("maxCastPerTarget", 0)),
        crit_chance=int(best.get("criticalHitProbability", 0)),
        element=infer_element(fr_description),
        tags=infer_tactical_tags(fr_name, fr_description),
    )


def build_dataset(
    raw_breeds: list[dict],
    raw_variants: list[dict],
    levels_by_id: dict[int, dict],
    lang: str = "fr",
) -> dict:
    """Assemble le dictionnaire sérialisable complet pour data/spells_<lang>.json."""
    variants_by_breed: dict[int, list[SpellVariantPair]] = {}
    for var in raw_variants:
        breed_id = int(var.get("breedId", 0))
        spells = var.get("spells", [])
        if not breed_id or not spells:
            continue
        primary = build_spell(spells[0], levels_by_id, lang=lang)
        variant = build_spell(spells[1], levels_by_id, lang=lang) if len(spells) > 1 else None
        pair = SpellVariantPair(
            variant_id=int(var.get("id", 0)),
            primary=primary,
            variant=variant,
        )
        variants_by_breed.setdefault(breed_id, []).append(pair)

    breeds: list[dict] = []
    for raw_b in sorted(raw_breeds, key=lambda b: int(b["id"])):
        bid = int(raw_b["id"])
        pairs = variants_by_breed.get(bid, [])
        breed = BreedInfo(
            id=bid,
            name=_pick(raw_b.get("shortName"), lang) or _pick(raw_b.get("name"), lang),
            description=_pick(raw_b.get("description"), lang),
            img_url=raw_b.get("img", ""),
            pairs=tuple(pairs),
        )
        breeds.append(breed.to_dict())

    return {
        "source": "DofusDB (https://dofusdb.fr)",
        "lang": lang,
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "breeds": breeds,
    }


def download_icons(dataset: dict, icons_dir: Path, client: httpx.Client) -> int:
    icons_dir.mkdir(parents=True, exist_ok=True)
    urls: set[str] = set()
    for breed in dataset["breeds"]:
        if breed.get("img_url"):
            urls.add(breed["img_url"])
        for pair in breed.get("pairs", []):
            for key in ("primary", "variant"):
                sp = pair.get(key)
                if sp and sp.get("img_url"):
                    urls.add(sp["img_url"])

    downloaded = 0
    for url in sorted(urls):
        filename = url.rsplit("/", 1)[-1]
        safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in filename)
        target = icons_dir / safe
        if target.exists():
            continue
        try:
            resp = client.get(url, timeout=10.0)
            if resp.status_code == 200 and resp.content:
                target.write_bytes(resp.content)
                downloaded += 1
        except httpx.HTTPError:
            pass
    return downloaded


def main() -> None:
    parser = argparse.ArgumentParser(description="Synchronise les sorts Dofus depuis DofusDB.")
    parser.add_argument("--with-icons", action="store_true", help="Pré-télécharge les icônes PNG.")
    parser.add_argument("--lang", choices=("fr", "en", "both"), default="both", help="Langues à exporter.")
    args = parser.parse_args()

    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    langs = ("fr", "en") if args.lang == "both" else (args.lang,)

    with httpx.Client(timeout=20.0, headers=HEADERS, follow_redirects=True) as client:
        print("1/3 Récupération des classes...")
        raw_breeds = fetch_breeds(client)
        print(f"    -> {len(raw_breeds)} classes trouvées")

        print("2/3 Récupération des paires sort/variante...")
        raw_variants = fetch_all_variants(client)
        print(f"    -> {len(raw_variants)} paires trouvées")

        # On ne récupère que le dernier spellLevel de chaque sort pour rester rapide et léger.
        target_level_ids: list[int] = []
        for var in raw_variants:
            for sp in var.get("spells", []):
                s_levels = sp.get("spellLevels", [])
                if s_levels:
                    target_level_ids.append(int(s_levels[-1]))

        print(f"3/3 Récupération des stats ({len(set(target_level_ids))} niveaux de sorts)...")
        levels_by_id = fetch_spell_levels(client, target_level_ids)

        first_dataset = None
        for lang in langs:
            dataset = build_dataset(raw_breeds, raw_variants, levels_by_id, lang=lang)
            if first_dataset is None:
                first_dataset = dataset
            out_path = data_dir / f"spells_{lang}.json"
            out_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Sauvegardé : {out_path}")

        if args.with_icons and first_dataset is not None:
            count = download_icons(first_dataset, data_dir / "icons", client)
            print(f"Icônes téléchargées : {count}")


if __name__ == "__main__":
    main()
