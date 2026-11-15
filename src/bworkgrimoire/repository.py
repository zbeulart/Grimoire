"""Chargement et filtrage ultra-rapide des classes et sorts Dofus."""

from __future__ import annotations

import json
from pathlib import Path

from bworkgrimoire.models import BreedInfo, SpellInfo, SpellVariantPair, normalize_text


def default_data_dir() -> Path:
    """Retourne le dossier data/ du projet (compatible dev et PyInstaller)."""
    import sys

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "data"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2] / "data"


class SpellRepository:
    """Stocke en mémoire les classes et fournit une recherche instantanée."""

    def __init__(self, breeds: list[BreedInfo]) -> None:
        self._breeds: list[BreedInfo] = sorted(breeds, key=lambda b: b.id)
        self._by_id: dict[int, BreedInfo] = {b.id: b for b in self._breeds}

    @classmethod
    def load_from_files(
        cls,
        spells_path: Path | None = None,
        tips_path: Path | None = None,
    ) -> SpellRepository:
        """Charge les données locales JSON (sorts + mémos tactiques par classe)."""
        data_dir = default_data_dir()
        spells_file = spells_path or (data_dir / "spells_fr.json")
        tips_file = tips_path or (data_dir / "class_tips.json")

        tips: dict[str, str] = {}
        if tips_file.exists():
            tips = json.loads(tips_file.read_text(encoding="utf-8"))

        if not spells_file.exists():
            return cls([])

        payload = json.loads(spells_file.read_text(encoding="utf-8"))
        breeds = [
            BreedInfo.from_dict(raw_breed, tip=tips.get(str(raw_breed["id"]), ""))
            for raw_breed in payload.get("breeds", [])
        ]
        return cls(breeds)

    @property
    def breeds(self) -> list[BreedInfo]:
        return list(self._breeds)

    def get_breed(self, breed_id: int) -> BreedInfo | None:
        return self._by_id.get(breed_id)

    @staticmethod
    def spell_matches(
        spell: SpellInfo,
        query: str = "",
        element: str = "Tous",
        tag: str = "Tous",
    ) -> bool:
        """Vérifie si un sort correspond aux filtres (recherche, élément, catégorie)."""
        if element != "Tous" and spell.element != element:
            return False
        if tag != "Tous" and tag not in spell.tags:
            return False
        q = normalize_text(query.strip())
        if q:
            haystack = normalize_text(
                f"{spell.name} {spell.description} {spell.element} {' '.join(spell.tags)}"
            )
            if q not in haystack:
                return False
        return True

    def filter_breeds(
        self,
        query: str = "",
        tag: str = "Tous",
    ) -> list[tuple[BreedInfo, int]]:
        """Filtre les classes par nom, mémo, catégorie ou sorts correspondants.

        Retourne (BreedInfo, nombre_de_sorts_correspondants).
        """
        q = normalize_text(query.strip())
        if not q and tag == "Tous":
            return [(b, 0) for b in self._breeds]

        results: list[tuple[BreedInfo, int]] = []
        for breed in self._breeds:
            spell_hits = sum(
                1
                for pair in breed.pairs
                for sp in pair.spells
                if self.spell_matches(sp, query=q, tag=tag)
            )
            meta_match = tag == "Tous" and bool(q) and (
                q in normalize_text(breed.name) or q in normalize_text(breed.tip)
            )
            if spell_hits > 0 or meta_match:
                results.append((breed, spell_hits))

        results.sort(key=lambda item: (-item[1], item[0].id))
        return results

    @classmethod
    def filter_pairs(
        cls,
        breed: BreedInfo,
        query: str = "",
        element: str = "Tous",
        tag: str = "Tous",
    ) -> list[SpellVariantPair]:
        """Filtre les paires Sort <-> Variante d'une classe selon recherche, élément et tag."""
        return [
            pair
            for pair in breed.pairs
            if any(cls.spell_matches(sp, query=query, element=element, tag=tag) for sp in pair.spells)
        ]
