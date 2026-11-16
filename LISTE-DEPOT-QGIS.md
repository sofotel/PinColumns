# Dépôt officiel QGIS — fichiers à joindre

Envoi sur https://plugins.qgis.org/ avec un compte OSGeo. Un seul fichier est téléversé : une archive ZIP. Elle contient un dossier `PinColumns`, pas les fichiers à la racine du ZIP.

```
PinColumns.zip
└── PinColumns/
    ├── __init__.py
    ├── metadata.txt
    ├── LICENSE
    ├── icon.png
    ├── pincolumns.py
    ├── figer_colonnes.py
    ├── textes.py
    ├── README.md
    ├── CHANGELOG.md
    └── i18n/
        ├── PinColumns_fr.ts
        ├── PinColumns_en.ts
        └── PinColumns_es.ts
```

## Obligatoire

| Fichier | Rôle |
| --- | --- |
| `__init__.py` | Point d'entrée, fonction `classFactory` |
| `metadata.txt` | Nom, version, auteur, description |
| `LICENSE` | Licence, sans extension. Le nom `LICENSE.txt` est refusé |
| `icon.png` | Icône déclarée dans `metadata.txt` |
| `pincolumns.py` | Bouton de la table |
| `figer_colonnes.py` | Figement des colonnes |
| `textes.py` | Textes traduits |
| `i18n/PinColumns_fr.ts` | Français |
| `i18n/PinColumns_en.ts` | Anglais |
| `i18n/PinColumns_es.ts` | Espagnol |

`LICENSE` est la GPL version 2 ou ultérieure. `metadata.txt` contient déjà `repository=https://github.com/sofotel/PinColumns`.

## Utile, pas bloquant

| Fichier | Rôle |
| --- | --- |
| `README.md` | Mode d'emploi |
| `CHANGELOG.md` | Historique. Le texte court est déjà dans `metadata.txt` |

`experimental=True` est déjà dans `metadata.txt`. Le plugin n'apparaît que si l'utilisateur affiche les extensions expérimentales.

## Ne pas mettre dans le ZIP

- `__pycache__/` et les fichiers `.pyc`
- `.git/`
- `symbology-style.db`
- `Icon1.png` (l'icône utilisée est `icon.png`)
- `test/`
- `.cursorrules`
- `BRIEF-IA.md`
- `ARCHITECTURE.md`
- `PinColumns.code-workspace`
- `.gitignore`
- `i18n/.gitkeep`
- ce fichier, `LISTE-DEPOT-QGIS.md`
