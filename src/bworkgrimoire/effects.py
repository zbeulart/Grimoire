"""Mise en forme des effets de sorts DofusDB en lignes lisibles, comme l'infobulle du jeu.

Chaque ligne rendue est un triplet ``[html, kind, element]`` :
- ``html``    : texte de l'effet (valeurs en <b>, noms d'états/sorts en <b class="nm">,
                durée en <span class="dur">, icône de tour en <i class="t">) ;
- ``kind``    : "dmg", "heal", "state", "sum", "neg" ou "" (sert à la couleur de la puce) ;
- ``element`` : "feu", "eau", "air", "terre", "neutre", "multi" ou "" pour dommages et soins.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

EFFECT_ELEMENTS = {0: "neutre", 1: "terre", 2: "feu", 3: "eau", 4: "air", 5: "multi"}
STATE_EFFECTS = {950, 951, 952}
SUMMON_EFFECTS = {181, 1008, 1011, 405, 2796, 1097}
NO_EXTRA_EFFECT = 666  # « Pas d'effet supplémentaire » : bruit, jamais affiché
TURN_ICON = '<i class="t"></i>'
MAX_SUBSPELL_DEPTH = 2

_COND_RE = re.compile(r"\{\{~1~2([^}]*)\}\}")
_ANY_COND_RE = re.compile(r"\{\{[^}]*\}\}")
_SPRITE_TURN_RE = re.compile(r'&lt;sprite name="tour"&gt;')
_SPRITE_RE = re.compile(r"&lt;sprite[^&]*&gt;")


def _fr(mapping: object) -> str:
    if isinstance(mapping, dict):
        return mapping.get("fr") or ""
    return mapping if isinstance(mapping, str) else ""


@dataclass
class EffectCatalog:
    """Données brutes DofusDB nécessaires au rendu des effets."""

    spells: dict[int, dict] = field(default_factory=dict)  # id -> objet "spells"
    levels: dict[int, dict] = field(default_factory=dict)  # id -> objet "spell-levels"
    effects: dict[int, dict] = field(default_factory=dict)  # id -> objet "effects"
    states: dict[int, str] = field(default_factory=dict)  # id -> nom d'état
    monsters: dict[int, str] = field(default_factory=dict)  # id -> nom d'invocation

    def spell_name(self, spell_id: int) -> str:
        spell = self.spells.get(int(spell_id))
        return _fr(spell.get("name")) if spell else ""

    def top_level(self, spell_id: int) -> dict | None:
        spell = self.spells.get(int(spell_id))
        if not spell or not spell.get("spellLevels"):
            return None
        return self.levels.get(int(max(spell["spellLevels"])))

    def template(self, effect_id: int) -> str:
        definition = self.effects.get(int(effect_id)) or {}
        return _fr(definition.get("description"))


def format_effect(effect: dict, catalog: EffectCatalog) -> list[str] | None:
    """Rend un effet de sort en ``[html, kind, element]`` (None si définition inconnue)."""
    definition = catalog.effects.get(int(effect["effectId"]))
    if not definition:
        return None
    tpl = _fr(definition.get("description"))
    p1, p2, p3 = int(effect.get("diceNum", 0)), int(effect.get("diceSide", 0)), int(effect.get("value", 0))
    eid = int(effect["effectId"])
    show_max = p2 > 0 and p2 > p1

    text = _COND_RE.sub((lambda m: m.group(1)) if show_max else "", tpl)
    text = text.replace("{{~ps}}", "s" if p1 > 1 else "").replace("{{~zs}}", "")
    text = _ANY_COND_RE.sub("", text)
    text = html.escape(text, quote=False)
    text = _SPRITE_TURN_RE.sub(TURN_ICON, text)
    text = _SPRITE_RE.sub("", text)

    def name_tag(value: str) -> str:
        return f'<b class="nm">{html.escape(value)}</b>'

    kind = ""
    if eid in STATE_EFFECTS:
        text = text.replace("#3", name_tag(catalog.states.get(p3, f"#{p3}")))
        kind = "state"
    elif eid in SUMMON_EFFECTS:
        text = text.replace("#1", name_tag(catalog.monsters.get(p1, "?")))
        kind = "sum"
    elif tpl.startswith("#1 :"):
        name = catalog.spell_name(p1)
        text = text.replace("#1", name_tag(name) if name else "", 1).lstrip(" :")
        text = text.replace("#3", f"<b>{p3}</b>")
    elif "#2" in tpl and "sort" in tpl and p2 == 0:
        text = text.replace("#2", name_tag(catalog.spell_name(p3) or str(p3)))
    else:
        text = (
            text.replace("#1", f"<b>{p1}</b>")
            .replace("#2", f"<b>{p2}</b>" if show_max else "")
            .replace("#3", f"<b>{p3}</b>")
        )
    text = re.sub(r"\s{2,}", " ", text).strip()

    low = tpl.lower()
    element_id = int(definition.get("elementId", -1))
    if not kind:
        if ("dommages" in low and element_id >= 0) or " vol " in f" {low}":
            kind = "dmg"
        elif "soin" in low and element_id >= 0:
            kind = "heal"
        elif text.startswith("-"):
            kind = "neg"

    duration = int(effect.get("duration", 0))
    if duration > 0:
        text += f' <span class="dur">– {duration}{TURN_ICON}</span>'
    elif duration < 0:
        text += ' <span class="dur">(infini)</span>'

    element = EFFECT_ELEMENTS.get(element_id, "") if kind in ("dmg", "heal") else ""
    return [text, kind, element]


def spell_effects(spell_id: int, catalog: EffectCatalog, critical: bool = False, depth: int = 0) -> list[list[str]]:
    """Effets visibles d'un sort (niveau maximal), sous-sorts lancés inclus."""
    level = catalog.top_level(spell_id)
    if not level or level.get("hideEffects"):
        return []
    lines: list[list[str]] = []
    for effect in level.get("criticalEffect" if critical else "effects", []):
        tpl = catalog.template(effect["effectId"]).strip()
        if tpl == "#1":  # « lance un sort » : on affiche les effets du sous-sort
            if effect.get("visibleInTooltip") and depth < MAX_SUBSPELL_DEPTH:
                lines += spell_effects(effect["diceNum"], catalog, critical, depth + 1)
            continue
        if not effect.get("visibleInTooltip") or int(effect["effectId"]) == NO_EXTRA_EFFECT:
            continue
        rendered = format_effect(effect, catalog)
        if rendered and rendered[0]:
            lines.append(rendered)
    return lines


def spell_tooltip_data(spell_id: int, catalog: EffectCatalog) -> dict:
    """Données d'infobulle d'un sort : effets normaux/critiques, cumul max et rang."""
    level = catalog.top_level(spell_id) or {}
    fx = spell_effects(spell_id, catalog)
    cfx = spell_effects(spell_id, catalog, critical=True)
    has_crit = int(level.get("criticalHitProbability", 0)) > 0
    return {
        "fx": fx,
        "cfx": cfx if has_crit and cfx != fx else [],
        "stack": int(level.get("maxStack", 0) or 0),
        "grade": int(level.get("grade", 0) or 0),
    }
