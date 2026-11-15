"""Tests du script de synchronisation DofusDB avec données mockées."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_dofusdb  # noqa: E402


def test_build_dataset_picks_highest_grade() -> None:
    raw_breeds = [
        {
            "id": 18,
            "shortName": {"fr": "Ouginak"},
            "description": {"fr": "Classe mêlée"},
            "img": "https://api.dofusdb.fr/img/breeds/symbol_18.png",
        }
    ]
    raw_variants = [
        {
            "id": 99,
            "breedId": 18,
            "spells": [
                {
                    "id": 1001,
                    "name": {"fr": "Morsure"},
                    "description": {"fr": "Occasionne des dommages Terre et applique Érosion."},
                    "img": "https://api.dofusdb.fr/img/spells/sort_1.png",
                    "spellLevels": [5001, 5002],
                },
                {
                    "id": 1002,
                    "name": {"fr": "Proie"},
                    "description": {"fr": "Soigne les alliés qui attaquent la cible."},
                    "img": "https://api.dofusdb.fr/img/spells/sort_2.png",
                    "spellLevels": [5003],
                },
            ],
        }
    ]
    levels_by_id = {
        5001: {"id": 5001, "grade": 1, "apCost": 4, "minRange": 1, "range": 1},
        5002: {"id": 5002, "grade": 3, "apCost": 3, "minRange": 1, "range": 2, "castTestLos": False},
        5003: {"id": 5003, "grade": 1, "apCost": 2, "minRange": 1, "range": 6, "minCastInterval": 3},
    }

    dataset = sync_dofusdb.build_dataset(raw_breeds, raw_variants, levels_by_id)
    assert len(dataset["breeds"]) == 1
    ougi = dataset["breeds"][0]
    assert ougi["name"] == "Ouginak"
    pair = ougi["pairs"][0]
    assert pair["primary"]["ap_cost"] == 3
    assert pair["primary"]["max_range"] == 2
    assert pair["primary"]["requires_los"] is False
    assert pair["primary"]["element"] == "Terre"
    assert "Érosion" in pair["primary"]["tags"]
    assert pair["variant"]["cooldown"] == 3
