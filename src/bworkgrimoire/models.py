"""Modèles de données et détection automatique des éléments et tags tactiques."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


def normalize_text(text: str) -> str:
    """Normalise un texte en minuscules sans accents pour la recherche rapide."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


ELEMENT_LINE_RE = re.compile(
    r"(?:dommages?|degats|vol de vie|element|meilleur element)[^\n.]{0,60}"
)
ELEMENT_NAMES: dict[str, str] = {
    "feu": "Feu",
    "eau": "Eau",
    "air": "Air",
    "terre": "Terre",
    "neutre": "Neutre",
}

SPELL_LINK_RE = re.compile(r"\{\{[^}]*?::(?:<[^>]+>)?([^<{}]+?)(?:</[^>]+>)?\}\}")
SPRITE_RE = re.compile(r'<sprite\s+name="([^"]+)">')
HTML_TAG_RE = re.compile(r"</?[^>]+>")

TACTICAL_RULES: dict[str, tuple[str, ...]] = {
    "Érosion": ("erosion", "erode"),
    "Débuff": ("reduit la duree des effets", "reduire la duree des effets", "debuff"),
    "Pesanteur": ("pesanteur",),
    "Invulnérable": ("invulnerab",),
    "Bouclier": ("bouclier", "shield", "points de bouclier"),
    "Soin": ("soin", "rend des pdv", "points de vie", "soigne", "vol de vie", "vole de la vie"),
    "Placement": (
        "teleporte",
        "attire",
        "rapproche",
        "repousse",
        "echange de position",
        "echange sa position",
        "echange leurs positions",
        "pousse",
        "porte",
        "jette",
    ),
    "Retrait PA/PM": (
        "retire des pa",
        "retire des pm",
        "vole des pa",
        "vole des pm",
        "retrait pa",
        "retrait pm",
        "rall",
    ),
    "Invocation": ("invoque",),
    "Boost": ("augmente les dommages", "puissance", "donne des pa", "donne des pm", "critique"),
}


def clean_description(text: str) -> str:
    """Nettoie les balises internes Dofus ({{spell,...}}, <sprite>, <color>) pour l'affichage."""
    cleaned = SPELL_LINK_RE.sub(r"\1", text.replace("\xa0", " "))
    cleaned = SPRITE_RE.sub(lambda m: f"[{m.group(1).capitalize()}]", cleaned)
    cleaned = HTML_TAG_RE.sub("", cleaned)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def infer_element(description: str) -> str:
    """Déduit l'élément principal d'un sort à partir de sa description française."""
    norm = normalize_text(description)
    if "meilleur element" in norm:
        return "Multi"
    found: set[str] = set()
    for segment in ELEMENT_LINE_RE.findall(norm):
        for key, label in ELEMENT_NAMES.items():
            if re.search(rf"\b{key}\b", segment):
                found.add(label)
    if len(found) == 1:
        return next(iter(found))
    if len(found) > 1:
        return "Multi"
    return "Utilitaire"


def infer_tactical_tags(name: str, description: str) -> tuple[str, ...]:
    """Déduit des tags tactiques utiles en combat (Érosion, Débuff, Placement...)."""
    norm = normalize_text(f"{name} {description}")
    tags = [tag for tag, kws in TACTICAL_RULES.items() if any(kw in norm for kw in kws)]
    return tuple(tags)


@dataclass(frozen=True)
class SpellInfo:
    """Représente un sort (niveau maximal) avec ses caractéristiques de combat."""

    id: int
    name: str
    description: str
    img_url: str
    ap_cost: int = 0
    min_range: int = 0
    max_range: int = 0
    range_modifiable: bool = False
    cast_in_line: bool = False
    cast_in_diagonal: bool = False
    requires_los: bool = True
    cooldown: int = 0
    max_per_turn: int = 0
    max_per_target: int = 0
    crit_chance: int = 0
    element: str = "Utilitaire"
    tags: tuple[str, ...] = field(default_factory=tuple)

    def format_range(self) -> str:
        """Formate la portée du sort (ex. '1-5 PO*')."""
        base = str(self.max_range) if self.min_range == self.max_range else f"{self.min_range}-{self.max_range}"
        suffix = "*" if self.range_modifiable else ""
        return f"{base} PO{suffix}"

    @classmethod
    def from_dict(cls, raw: dict) -> SpellInfo:
        name = raw["name"]
        description = clean_description(raw.get("description", ""))
        element = raw.get("element") or infer_element(description)
        tags = infer_tactical_tags(name, description)
        return cls(
            id=int(raw["id"]),
            name=name,
            description=description,
            img_url=raw.get("img_url", ""),
            ap_cost=int(raw.get("ap_cost", 0)),
            min_range=int(raw.get("min_range", 0)),
            max_range=int(raw.get("max_range", 0)),
            range_modifiable=bool(raw.get("range_modifiable", False)),
            cast_in_line=bool(raw.get("cast_in_line", False)),
            cast_in_diagonal=bool(raw.get("cast_in_diagonal", False)),
            requires_los=bool(raw.get("requires_los", True)),
            cooldown=int(raw.get("cooldown", 0)),
            max_per_turn=int(raw.get("max_per_turn", 0)),
            max_per_target=int(raw.get("max_per_target", 0)),
            crit_chance=int(raw.get("crit_chance", 0)),
            element=element,
            tags=tags,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "img_url": self.img_url,
            "ap_cost": self.ap_cost,
            "min_range": self.min_range,
            "max_range": self.max_range,
            "range_modifiable": self.range_modifiable,
            "cast_in_line": self.cast_in_line,
            "cast_in_diagonal": self.cast_in_diagonal,
            "requires_los": self.requires_los,
            "cooldown": self.cooldown,
            "max_per_turn": self.max_per_turn,
            "max_per_target": self.max_per_target,
            "crit_chance": self.crit_chance,
            "element": self.element,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class SpellVariantPair:
    """Paire Sort principal / Variante (ou sort unique si aucune variante)."""

    variant_id: int
    primary: SpellInfo
    variant: SpellInfo | None = None

    @property
    def spells(self) -> tuple[SpellInfo, ...]:
        return (self.primary, self.variant) if self.variant else (self.primary,)

    @classmethod
    def from_dict(cls, raw: dict) -> SpellVariantPair:
        variant_raw = raw.get("variant")
        return cls(
            variant_id=int(raw.get("variant_id", 0)),
            primary=SpellInfo.from_dict(raw["primary"]),
            variant=SpellInfo.from_dict(variant_raw) if variant_raw else None,
        )

    def to_dict(self) -> dict:
        return {
            "variant_id": self.variant_id,
            "primary": self.primary.to_dict(),
            "variant": self.variant.to_dict() if self.variant else None,
        }


@dataclass(frozen=True)
class BreedInfo:
    """Représente une classe Dofus et ses paires de sorts."""

    id: int
    name: str
    description: str
    img_url: str
    pairs: tuple[SpellVariantPair, ...] = field(default_factory=tuple)
    tip: str = ""
    # Sorts propres à la classe hors variantes, par deux (Bellaphone : Bellaura -> sort de lignée).
    auras: tuple[SpellVariantPair, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, raw: dict, tip: str = "") -> BreedInfo:
        pairs = tuple(SpellVariantPair.from_dict(p) for p in raw.get("pairs", []))
        return cls(
            id=int(raw["id"]),
            name=raw["name"],
            description=raw.get("description", ""),
            img_url=raw.get("img_url", ""),
            pairs=pairs,
            tip=tip or raw.get("tip", ""),
            auras=tuple(SpellVariantPair.from_dict(p) for p in raw.get("auras", [])),
        )

    def to_dict(self) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "img_url": self.img_url,
            "pairs": [p.to_dict() for p in self.pairs],
        }
        if self.auras:
            data["auras"] = [p.to_dict() for p in self.auras]
        return data
