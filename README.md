# Grimoire

Petit grimoire overlay hors-ligne des **19 classes et sorts Dofus**, pensé comme plugin communautaire pour **Bworkshop** (`bworkshop.app`).

## Fonctionnalités
- **1 clic = fiche de classe** : grille des 19 classes dès l'ouverture (ex. Ouginak, Xélor, Forgelance...).
- **Paires Sort | Variante** : coûts en **PA**, **PO**, **Ligne de vue (LDV)**, **Relance (CD)**, élément et infobulles d'effets normaux/critiques.
- **Filtres instantanés** : recherche par nom ou effet (`érosion`, `pesanteur`, `invocation`, `pousse`...) et filtres d'éléments.
- **Mode livre flottant (widget)** : se replie en petit livre flottant toujours au-dessus du jeu (glisser pour déplacer, 1 clic pour rouvrir) + icône près de l'horloge Windows.
- **100 % hors-ligne & conforme CGU Ankama** : toutes les données, polices et 855 icônes sont embarquées en local ; aucune lecture mémoire, aucune interception réseau, aucune automatisation.

## Lancer en local
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"

# (Optionnel) Resynchroniser les sorts, icônes et effets depuis DofusDB
python scripts/sync_dofusdb.py --with-icons
python scripts/sync_effects.py

# Lancer Grimoire
python main.py
```

## Générer l'installateur Windows (`Grimoire-Setup.exe`)
Nécessite `pyinstaller` (dans `.venv`) et **Inno Setup 6** :
```powershell
.\scripts\build_installer.ps1
```
Les fichiers générés se trouvent dans `dist/` (`Grimoire-Setup.exe`, `Grimoire-Windows.zip` et `SHA256SUMS.txt`).

## Tests
```powershell
pytest
```

## Crédits & Licence
- Code source sous licence **MIT**.
- Données et icônes de classes/sorts : **DofusDB** (`https://dofusdb.fr`) — usage non commercial avec attribution.
- Projet communautaire indépendant, non affilié à Ankama Games.
