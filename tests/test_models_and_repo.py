"""Tests unitaires pour les modèles, la normalisation et le SpellRepository."""

import json
from pathlib import Path

from bworkgrimoire.models import (
    BreedInfo,
    SpellInfo,
    SpellVariantPair,
    clean_description,
    infer_element,
    infer_tactical_tags,
)
from bworkgrimoire.repository import SpellRepository


def _sample_breed() -> BreedInfo:
    s1 = SpellInfo(
        id=1,
        name="Molosse",
        description="Occasionne des dommages Eau et applique Érosion.",
        img_url="",
        ap_cost=3,
        min_range=1,
        max_range=4,
        range_modifiable=True,
        element=infer_element("Occasionne des dommages Eau et applique Érosion."),
        tags=infer_tactical_tags("Molosse", "Occasionne des dommages Eau et applique Érosion."),
    )
    s2 = SpellInfo(
        id=2,
        name="Limier",
        description="Occasionne des dommages Air et retire des PM.",
        img_url="",
        ap_cost=4,
        min_range=1,
        max_range=3,
        element=infer_element("Occasionne des dommages Air et retire des PM."),
        tags=infer_tactical_tags("Limier", "Occasionne des dommages Air et retire des PM."),
    )
    return BreedInfo(
        id=18,
        name="Ouginak",
        description="Chasseur",
        img_url="",
        tip="Monte sa jauge de Rage et pose Proie.",
        pairs=(SpellVariantPair(variant_id=10, primary=s1, variant=s2),),
    )


def test_infer_element_and_tags() -> None:
    assert infer_element("Occasionne des dommages Feu aux ennemis.") == "Feu"
    assert infer_element("Occasionne des dommages Feu et Eau.") == "Multi"
    assert infer_element("Téléporte le lanceur.") == "Utilitaire"

    tags = infer_tactical_tags("Proie", "Applique Pesanteur, Érosion et repousse la cible.")
    assert "Pesanteur" in tags
    assert "Érosion" in tags
    assert "Placement" in tags

    debuff_tags = infer_tactical_tags("Régulateur", "Réduit la durée des effets sur la cible.")
    assert "Débuff" in debuff_tags

    assert clean_description('Consomme {{spell,24510,1::<color=#ebc304>téléfrag</color>}} <sprite name="terre">') == "Consomme téléfrag [Terre]"


def test_repository_filtering_and_json_loading(tmp_path: Path) -> None:
    ougi = _sample_breed()
    spells_file = tmp_path / "spells_fr.json"
    tips_file = tmp_path / "class_tips.json"
    spells_file.write_text(json.dumps({"breeds": [ougi.to_dict()]}), encoding="utf-8")
    tips_file.write_text(json.dumps({"18": "Rage et Proie"}), encoding="utf-8")

    repo = SpellRepository.load_from_files(spells_file, tips_file)
    assert len(repo.breeds) == 1
    loaded = repo.get_breed(18)
    assert loaded is not None
    assert loaded.tip == "Rage et Proie"

    assert len(repo.filter_breeds("ougi")) == 1
    assert len(repo.filter_breeds("rage")) == 1
    erosion_breeds = repo.filter_breeds("erosion")
    assert len(erosion_breeds) == 1
    assert erosion_breeds[0][1] == 1
    assert len(repo.filter_breeds(tag="Retrait PA/PM")) == 1
    assert len(repo.filter_breeds("xelor")) == 0

    assert len(repo.filter_pairs(loaded, query="erosion")) == 1
    assert len(repo.filter_pairs(loaded, element="Eau")) == 1
    assert len(repo.filter_pairs(loaded, element="Feu")) == 0
    assert len(repo.filter_pairs(loaded, tag="Retrait PA/PM")) == 1
