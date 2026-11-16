# Changelog - PinColumns

## 0.2 - 2026-11-16

Bouton à flèche dans la barre de la table attributaire. Trois modes : figer la colonne et celles d'avant, figer seulement cette colonne, figer la colonne et celles d'après.

Le figement est enregistré sur la couche (`pincolumns/mode`, `pincolumns/champ`) et reposé à la réouverture de la table. Fermer la table conserve le choix. « Libérer les colonnes » l'efface et décoche le menu. Le projet doit être enregistré pour le garder après la fermeture de QGIS.

Masquer une colonne figée n'écrit plus une largeur nulle dans la configuration de la table. Une largeur déjà nulle est réparée à la réouverture.

## 0.1 - 2026-11-15

Structure du plugin préparée. Remplacée par le comportement du bouton.
