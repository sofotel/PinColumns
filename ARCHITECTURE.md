# Architecture - PinColumns

**Version :** 0.4

```
Table attributaire ouverte
        │
        ▼
SurveillantTables          pincolumns.py
        │  bouton + flèche
        │  lecture pincolumns/mode et pincolumns/champ
        ▼
FigementColonnes           figer_colonnes.py
        │
        ▼
Seconde vue dans le séparateur de la table
```

`pincolumns.py` ajoute le bouton sur la barre `mToolbar` de chaque `QgsAttributeTableDialog`. Le même menu est ajouté au clic droit de l'en-tête, après celui de QGIS. À l'ouverture, une restauration unique repose le figement enregistré sur la couche.

`figer_colonnes.py` place les colonnes tenues dans une vue à côté de la table (`pincolumnsVueFigee`), et masque ces colonnes dans la vue qui défile. `avant` et `seule` sont à gauche. `apres` est à droite, avant le panneau conditionnel.

La vue figée est un `QTableView`. QGIS ne lui donne pas ses menus : `pincolumns.py` les reconstruit au clic droit de l'en-tête et réutilise `willShowContextMenu` pour les cellules. Le clic sur un numéro de ligne émet `requestRepaint`, pas `selectionChanged`. La vue figée écoute ce signal pour repeindre la surbrillance.

Le masquage bloque les signaux de la vue. QGIS écoute le changement de largeur et l'écrit dans la configuration de la table : une colonne masquée y vaudrait 0 et disparaîtrait à la réouverture. La fermeture de la table rend les colonnes et réécrit leur largeur, sans effacer la préférence. « Libérer les colonnes » efface `pincolumns/mode` et `pincolumns/champ`.

La préférence vit sur la couche du projet. Elle entre dans le qgz quand l'utilisateur enregistre le projet.

## Tests

`test/test_repartition.py` vérifie le partage gauche, seule et droite. `test/test_preference.py` vérifie l'enregistrement sur la couche et la relecture après écriture du projet.
