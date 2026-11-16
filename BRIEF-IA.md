# BRIEF-IA - PinColumns

**MAJ :** 2026-11-16

## But

Figer des colonnes dans la table attributaire de QGIS.

Le bouton est dans la barre de la table, pas dans une fenêtre du plugin. Un clic exécute le mode actif. La flèche ouvre les trois modes et « Libérer les colonnes ».

L'infobulle du bouton principal reste « Figer les colonnes ». Ne pas y remettre le texte long du mode. Les infobulles longues sont sur les entrées du menu.

Les textes visibles passent par `traduire`. Le français est la source. Anglais et espagnol sont dans `i18n/PinColumns_en.ts` et `i18n/PinColumns_es.ts`. La langue vient de QGIS.

## Modes

- `avant` : la colonne choisie et celles d'avant, à gauche. Mode par défaut.
- `seule` : seulement la colonne choisie, à gauche.
- `apres` : la colonne choisie et celles d'après, à droite. Libellé du menu : « Figer les colonnes d'après ».

La colonne repère est le dernier en-tête cliqué, sinon la cellule active. La colonne d'actions n'est pas figée. Les numéros de ligne restent sur la vue native : l'en-tête vertical de la vue figée reste caché.

## Projet

Pour chaque couche, le mode et le nom du champ repère sont dans les propriétés `pincolumns/mode` et `pincolumns/champ`. Ne pas renommer ces clés.

Fermer la table appelle `abandonner` : les colonnes redeviennent visibles, la préférence reste. « Libérer les colonnes » appelle `liberer`, `effacerPreference` et décoche le menu. Une préférence identique ne remarque pas le projet comme modifié.

`setDirty` est posé quand la préférence change. Elle est écrite dans le qgz seulement à l'enregistrement du projet. Sans le plugin, QGIS ignore ces propriétés et n'a aucune colonne masquée par PinColumns.

## Technique

`pincolumns.py` pose le bouton. `figer_colonnes.py` place une seconde vue dans le séparateur de la table.

Les colonnes figées sont masquées sur la vue qui défile, et l'inverse sur la vue figée, par `setColumnHidden` seulement. Ne pas passer par `QgsAttributeTableConfig.setColumnHidden`. Les signaux de la vue sont bloqués pendant ce masquage, sinon QGIS enregistre une largeur 0 et la colonne disparaît. À la fermeture, les largeurs réelles sont réécrites avec les signaux actifs. `reparerLargeursNulles` répare une largeur déjà enregistrée à 0.

La restauration se fait une seule fois, par `QTimer.singleShot(0)`. Un `modelReset` repose le figement si une préférence existe. Ne pas le reposer après une libération utilisateur.

La couche se lit via `sip.cast` vers `QgsAttributeTableFilterModel`, puis `layer()`. La sélection figée exige un `QgsFeatureSelectionModel`.

Les erreurs passent par `tracerErreur` (journal QGIS « PinColumns »). Pas de `print`, pas de fichier journal.

## Tests

Depuis le dossier du plugin, avec le Python de QGIS :

`python-qgis-ltr.bat -m unittest discover -s test -v`

`test/test_repartition.py` couvre le partage des colonnes. `test/test_preference.py` couvre la lecture, l'écriture, l'effacement et la survie dans un fichier de projet.
