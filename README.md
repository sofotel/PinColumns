# PinColumns

Plugin QGIS pour figer des colonnes dans une table attributaire. Les colonnes choisies restent visibles pendant le défilement horizontal.

## Usage

Open an attribute table and click a column header, or right-click it. The toolbar button freezes that column and the ones before it. The menu can freeze only that column, or that column and the ones after it. Frozen columns keep the same right-click, on the header and on cells. A selected row stays highlighted on both sides. Closing the table keeps the choice. Unfreeze columns clears it. Save the project to keep the freeze.

## Utilisation

1. Ouvrir la table attributaire.
2. Cliquer l'en-tête de la colonne qui sert de repère. Sans clic, la cellule active est utilisée.
3. Cliquer le bouton en bout de barre. Par défaut, cette colonne et celles d'avant restent à gauche.
4. La flèche à côté du bouton propose les autres modes, ou libère les colonnes.
5. Le clic droit sur un en-tête de colonne ouvre le même menu, pour la colonne sous le curseur. Il reste disponible sur la partie figée, en-tête et cellules : masquer, largeur, tri, et figement.

Cliquer le numéro de ligne sélectionne la ligne des deux côtés. La surbrillance de la partie figée suit celle de la table.

Modes :

- **Figer cette colonne et celles d'avant** : elles restent à gauche, les colonnes de droite défilent.
- **Figer seulement cette colonne** : elle reste à gauche, les autres défilent.
- **Figer cette colonne et celles d'après** : cette colonne et celles d'après restent à droite, les précédentes défilent.

La colonne d'actions n'est pas figée. Les numéros de ligne restent ceux de la table QGIS. Il faut laisser au moins une colonne qui défile.

L'infobulle du bouton est « Figer les colonnes ». Le détail de chaque mode est dans le menu. Boutons et infobulles suivent la langue de QGIS : français, anglais ou espagnol.

## Mémoire

Le choix est enregistré sur la couche, dans le projet : le mode et le nom du champ repère. Fermer la table puis la rouvrir repose le même figement. **Libérer les colonnes** retire ce choix et décoche le menu.

QGIS marque le projet comme modifié. Le figement survit à la fermeture de QGIS seulement si le projet est enregistré.

Sans le plugin, la table défile normalement. QGIS ignore ces propriétés, et les colonnes ne sont pas masquées.
