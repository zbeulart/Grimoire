"""Génère la page du grimoire (data/web/grimoire.html) avec les données des classes et sorts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from bworkgrimoire.models import BreedInfo, SpellInfo
from bworkgrimoire.repository import SpellRepository, default_data_dir


def web_dir(data_dir: Path | None = None) -> Path:
    return (data_dir or default_data_dir()) / "web"


def load_effects(data_dir: Path | None = None) -> dict[str, dict]:
    """Charge data/spell_effects_fr.json (effets exacts par id de sort), vide si absent."""
    path = (data_dir or default_data_dir()) / "spell_effects_fr.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("spells", {})


class IconResolver:
    """Remplace l'URL distante d'une icône par le fichier local s'il existe (hors-ligne)."""

    def __init__(self, folders: list[Path], prefix: str | None = None) -> None:
        self._folders = [f for f in folders if f and f.exists()]
        self._prefix = prefix

    def __call__(self, url: str) -> str:
        if not url:
            return ""
        filename = url.rsplit("/", 1)[-1]
        safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in filename)
        for folder in self._folders:
            candidate = folder / safe
            if candidate.exists():
                return f"{self._prefix}{safe}" if self._prefix is not None else candidate.resolve().as_uri()
        return url


def _spell_payload(spell: SpellInfo, effects: dict[str, dict], icon: IconResolver) -> dict:
    extra = effects.get(str(spell.id), {})
    return {
        "name": spell.name,
        "ap": spell.ap_cost,
        "rmin": spell.min_range,
        "rmax": spell.max_range,
        "rmod": spell.range_modifiable,
        "cd": spell.cooldown,
        "mt": spell.max_per_turn,
        "mtg": spell.max_per_target,
        "los": spell.requires_los,
        "line": spell.cast_in_line,
        "crit": spell.crit_chance,
        "stack": extra.get("stack", 0),
        "grade": extra.get("grade", 0),
        "el": spell.element,
        "img": icon(spell.img_url),
        "tags": list(spell.tags),
        "desc": spell.description,
        "fx": extra.get("fx", []),
        "cfx": extra.get("cfx", []),
    }


def _sort_key(breed: BreedInfo) -> str:
    return breed.name.replace("É", "E").replace("é", "e")


def build_payload(repo: SpellRepository, effects: dict[str, dict], icon: IconResolver) -> dict:
    """Données injectées dans la page : classes triées par nom, paires sort/variante."""
    breeds = []
    for breed in sorted(repo.breeds, key=_sort_key):
        pairs = [
            {"a": _spell_payload(p.primary, effects, icon), "b": _spell_payload(p.variant, effects, icon)}
            for p in breed.pairs
            if p.variant is not None
        ]
        if pairs:
            breeds.append({"name": breed.name, "img": icon(breed.img_url), "pairs": pairs})
    return {"breeds": breeds}


def render_page(template: str, payload: dict, host: str, base_url: str) -> str:
    """Remplit le modèle HTML : données, mode d'hébergement ("qt" ou "web") et chemins locaux."""
    html = template.replace("/*DATA*/null", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("/*HOST*/'web'", json.dumps(host))
    html = html.replace("{{WEB_BASE}}", base_url)
    channel = '<script src="qrc:///qtwebchannel/qwebchannel.js"></script>' if host == "qt" else ""
    return html.replace("<!--QWEBCHANNEL-->", channel)


def write_page(repo: SpellRepository, out_path: Path, host: str = "qt", data_dir: Path | None = None,
               extra_icon_dirs: list[Path] | None = None) -> Path:
    """Écrit la page prête à charger (fichier local) et retourne son chemin."""
    data_dir = data_dir or default_data_dir()
    folder = web_dir(data_dir)
    template = (folder / "grimoire.html").read_text(encoding="utf-8")
    icon = IconResolver([data_dir / "icons", *(extra_icon_dirs or [])])
    payload = build_payload(repo, load_effects(data_dir), icon)
    base_url = folder.resolve().as_uri() + "/"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_page(template, payload, host, base_url), encoding="utf-8")
    return out_path


def export_web_bundle(repo: SpellRepository, out_dir: Path, data_dir: Path | None = None) -> Path:
    """Exporte une version Web statique autonome (index.html + fonts/ + icons/) dans out_dir."""
    data_dir = data_dir or default_data_dir()
    folder = web_dir(data_dir)
    template = (folder / "grimoire.html").read_text(encoding="utf-8")

    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(folder / "fonts", out_dir / "fonts", dirs_exist_ok=True)
    book_svg = folder / "book_closed.svg"
    if book_svg.exists():
        shutil.copy2(book_svg, out_dir / "book_closed.svg")

    icons_src = data_dir / "icons"
    if icons_src.exists():
        shutil.copytree(icons_src, out_dir / "icons", dirs_exist_ok=True)

    icon = IconResolver([icons_src], prefix="icons/")
    payload = build_payload(repo, load_effects(data_dir), icon)
    index_path = out_dir / "index.html"
    index_path.write_text(render_page(template, payload, host="web", base_url=""), encoding="utf-8")
    return index_path
