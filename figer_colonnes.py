# -*- coding: utf-8 -*-
"""Fige des colonnes de la table attributaire.

La vue principale de QGIS recalcule elle-meme ses marges. Une seconde
vue est donc placee a cote, dans le separateur deja present, au lieu
d'etre dessinee par-dessus les cellules.
"""

import traceback
from typing import Optional

from qgis.PyQt import sip
from qgis.PyQt.QtCore import QTimer, Qt
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QSplitter,
    QTableView,
)
from qgis.core import Qgis, QgsAttributeTableConfig, QgsMessageLog, QgsProject
from qgis.gui import (
    QgsAttributeTableDelegate,
    QgsAttributeTableFilterModel,
    QgsAttributeTableModel,
    QgsFeatureSelectionModel,
)

try:
    from .textes import traduire
except ImportError:
    from textes import traduire

MODE_AVANT = "avant"
MODE_SEULE = "seule"
MODE_APRES = "apres"
MODES = (MODE_AVANT, MODE_SEULE, MODE_APRES)

CLE_MODE = "pincolumns/mode"
CLE_CHAMP = "pincolumns/champ"

_JOURNAL = "PinColumns"
_HAUTEUR_MAX_SYNCHRO = 2000


def tracerErreur(contexte: str, erreur: BaseException) -> None:
    """Ecrit l'erreur et sa pile dans le journal QGIS."""
    QgsMessageLog.logMessage(
        f"{contexte} : {erreur}\n{traceback.format_exc()}",
        _JOURNAL,
        Qgis.Critical,
    )


def tracerRepli(contexte: str, erreur: BaseException) -> None:
    """Note un repli de lecture dans le journal, sans interrompre le figement."""
    QgsMessageLog.logMessage(
        f"{contexte} : {erreur}",
        _JOURNAL,
        Qgis.Warning,
    )


def repartirColonnes(indicesVisibles: list, indiceCible: int, mode: str) -> Optional[tuple]:
    """Separe les colonnes visibles en colonnes figees et defilantes.

    :param indicesVisibles: indices logiques, dans l'ordre visuel
    :param indiceCible: indice logique de la colonne choisie
    :param mode: avant, seule ou apres
    :return: (figees, defilantes) ou None si le partage est impossible
    """
    if mode not in MODES or not indicesVisibles:
        return None
    if indiceCible not in indicesVisibles:
        return None
    position = indicesVisibles.index(indiceCible)
    if mode == MODE_AVANT:
        figees = list(indicesVisibles[: position + 1])
        defilantes = list(indicesVisibles[position + 1 :])
    elif mode == MODE_SEULE:
        figees = [indiceCible]
        defilantes = [indice for indice in indicesVisibles if indice != indiceCible]
    else:
        figees = list(indicesVisibles[position:])
        defilantes = list(indicesVisibles[:position])
    if not figees or not defilantes:
        return None
    return figees, defilantes


def estSupprime(widget) -> bool:
    """Vrai si le widget C++ n'existe plus."""
    if widget is None:
        return True
    try:
        return sip.isdeleted(widget)
    except Exception:
        return True


def _indiceColonneAction(vue) -> int:
    filtre = _modeleFiltre(vue)
    if filtre is None or not hasattr(filtre, "actionColumnIndex"):
        return -1
    try:
        return int(filtre.actionColumnIndex())
    except Exception:
        return -1


def listerColonnesVisibles(vue) -> list:
    """Indices logiques des colonnes de champ visibles, dans l'ordre affiche."""
    if estSupprime(vue):
        return []
    entete = vue.horizontalHeader()
    if entete is None:
        return []
    colonneAction = _indiceColonneAction(vue)
    resultat = []
    for visuel in range(entete.count()):
        logique = entete.logicalIndex(visuel)
        if logique < 0 or logique == colonneAction:
            continue
        if vue.isColumnHidden(logique) or entete.isSectionHidden(logique):
            continue
        resultat.append(logique)
    return resultat


def _modeleFiltre(vue):
    """Modele de la table, type correctement pour acceder a la couche."""
    if estSupprime(vue):
        return None
    modele = vue.model()
    if modele is None:
        return None
    try:
        filtre = sip.cast(modele, QgsAttributeTableFilterModel)
        if filtre is not None:
            return filtre
    except Exception as erreur:
        tracerRepli("Lecture du modele filtre", erreur)
    return modele


def coucheDeLaVue(vue):
    """Couche affichee par la table, ou None."""
    filtre = _modeleFiltre(vue)
    if filtre is None:
        return None
    try:
        couche = filtre.layer()
        if couche is not None:
            return couche
    except Exception as erreur:
        tracerRepli("Lecture de la couche", erreur)
    maitre = _modeleMaitre(vue)
    if maitre is None or maitre is filtre:
        return None
    try:
        return maitre.layer()
    except Exception:
        return None


def _modeleMaitre(vue):
    filtre = _modeleFiltre(vue)
    if filtre is None:
        return None
    try:
        maitre = filtre.masterModel()
        if maitre is not None:
            return maitre
    except Exception as erreur:
        tracerRepli("Lecture du modele maitre", erreur)
    try:
        maitre = sip.cast(filtre, QgsAttributeTableModel)
        if maitre is not None:
            return maitre
    except Exception as erreur:
        tracerRepli("Lecture du modele source", erreur)
    return filtre


def _colonneVue(vue, indiceMaitre: int) -> int:
    """Colonne de la vue pour une colonne du modele source."""
    if estSupprime(vue) or indiceMaitre < 0:
        return -1
    modele = vue.model()
    maitre = _modeleMaitre(vue)
    if (
        modele is not None
        and maitre is not None
        and hasattr(modele, "mapFromSource")
        and maitre.rowCount() > 0
    ):
        try:
            index = maitre.index(0, int(indiceMaitre))
            if index.isValid():
                proxy = modele.mapFromSource(index)
                if proxy.isValid():
                    return int(proxy.column())
        except Exception as erreur:
            tracerRepli("Correspondance de colonne", erreur)
    return int(indiceMaitre)


def _coucheProjet(couche):
    """Couche du projet qui porte les proprietes, sinon la couche recue."""
    if couche is None:
        return None
    try:
        projet = QgsProject.instance()
        if projet is None:
            return couche
        duProjet = projet.mapLayer(couche.id())
        if duProjet is not None:
            return duProjet
    except Exception:
        return couche
    return couche


def _nomsColonnes(vue) -> list:
    """Nom de champ pour chaque colonne du modele. Vide pour la colonne action."""
    if estSupprime(vue):
        return []
    modele = vue.model()
    couche = coucheDeLaVue(vue)
    if modele is None or couche is None:
        return []
    try:
        nombre = int(modele.columnCount())
    except Exception:
        return []
    if nombre <= 0:
        return []
    noms = [""] * nombre
    try:
        configNoms = []
        for colonne in couche.attributeTableConfig().columns():
            if colonne.hidden:
                continue
            if colonne.type == QgsAttributeTableConfig.Action:
                configNoms.append("")
            else:
                configNoms.append(colonne.name or "")
        action = _indiceColonneAction(vue)
        if action >= 0 and len(configNoms) == nombre - 1:
            configNoms.insert(min(max(action, 0), len(configNoms)), "")
        if len(configNoms) == nombre:
            noms = list(configNoms)
    except Exception as erreur:
        tracerErreur("Lecture des colonnes", erreur)
    champs = couche.fields()
    if modele.rowCount() > 0:
        for indice in range(nombre):
            if noms[indice]:
                continue
            nom = _nomParRole(modele, champs, indice)
            if nom:
                noms[indice] = nom
    for indice in range(nombre):
        if noms[indice]:
            continue
        nom = _nomParEntete(modele, champs, indice)
        if nom:
            noms[indice] = nom
    return noms


def _nomParRole(modele, champs, indice: int) -> str:
    try:
        index = modele.index(0, indice)
        if not index.isValid():
            return ""
        valeur = index.data(QgsAttributeTableModel.FieldIndexRole)
        if valeur is None:
            return ""
        indiceChamp = int(valeur)
        if indiceChamp < 0:
            return ""
        return champs.field(indiceChamp).name() or ""
    except Exception:
        return ""


def _nomParEntete(modele, champs, indice: int) -> str:
    try:
        libelle = str(modele.headerData(indice, Qt.Horizontal, Qt.DisplayRole) or "")
    except Exception:
        return ""
    if not libelle:
        return ""
    if champs.indexFromName(libelle) >= 0:
        return libelle
    for i in range(champs.count()):
        champ = champs.field(i)
        if champ.name() == libelle or (champ.alias() or "") == libelle:
            return champ.name()
    return ""


def nomChampColonne(vue, indice: int) -> str:
    """Nom du champ pour une colonne logique."""
    try:
        indice = int(indice)
    except (TypeError, ValueError):
        return ""
    noms = _nomsColonnes(vue)
    if 0 <= indice < len(noms):
        return noms[indice]
    return ""


def indiceColonneChamp(vue, nomChamp: str) -> int:
    """Colonne logique du champ, ou -1."""
    if not nomChamp:
        return -1
    try:
        return _nomsColonnes(vue).index(nomChamp)
    except ValueError:
        return -1


def reparerLargeursNulles(vue) -> None:
    """Rend visibles les colonnes dont la largeur enregistree est nulle.

    QGIS ecrit la largeur de la vue dans la couche. Masquer une colonne
    y laisse donc 0, et la colonne disparait a la reouverture.
    """
    if estSupprime(vue):
        return
    couche = coucheDeLaVue(vue)
    maitre = _modeleMaitre(vue)
    if couche is None or maitre is None or not hasattr(maitre, "fieldCol"):
        return
    try:
        colonnes = list(couche.attributeTableConfig().columns())
        champs = couche.fields()
    except Exception as erreur:
        tracerErreur("Lecture des largeurs", erreur)
        return
    entete = vue.horizontalHeader()
    defaut = 100
    if entete is not None:
        try:
            taille = int(entete.defaultSectionSize())
            if taille >= 24:
                defaut = taille
        except (TypeError, ValueError) as erreur:
            tracerRepli("Lecture de la largeur par defaut", erreur)
    repare = False
    for colonne in colonnes:
        try:
            if colonne.hidden or int(colonne.width) != 0 or not colonne.name:
                continue
            if colonne.type == QgsAttributeTableConfig.Action:
                continue
            indiceChamp = champs.indexFromName(colonne.name)
            if indiceChamp < 0:
                continue
            logique = _colonneVue(vue, int(maitre.fieldCol(indiceChamp)))
        except Exception as erreur:
            tracerRepli("Lecture d'une colonne", erreur)
            continue
        if logique < 0 or estSupprime(vue):
            continue
        try:
            if vue.isColumnHidden(logique) or vue.columnWidth(logique) > 0:
                continue
            vue.setColumnWidth(logique, defaut)
            repare = True
        except Exception as erreur:
            tracerErreur("Reparation d'une largeur", erreur)
    if repare:
        _marquerProjet()


def lirePreference(couche) -> tuple:
    """Mode et nom de champ enregistres sur la couche."""
    couche = _coucheProjet(couche)
    if couche is None:
        return "", ""
    mode = str(couche.customProperty(CLE_MODE, "") or "").strip()
    champ = str(couche.customProperty(CLE_CHAMP, "") or "").strip()
    return mode, champ


def _marquerProjet() -> None:
    projet = QgsProject.instance()
    if projet is not None:
        projet.setDirty(True)


def enregistrerPreference(couche, mode: str, nomChamp: str) -> None:
    """Ecrit le figement dans le projet, via les proprietes de la couche."""
    couche = _coucheProjet(couche)
    if couche is None or mode not in MODES or not nomChamp:
        return
    ancienMode = str(couche.customProperty(CLE_MODE, "") or "").strip()
    ancienChamp = str(couche.customProperty(CLE_CHAMP, "") or "").strip()
    if ancienMode == mode and ancienChamp == nomChamp:
        return
    couche.setCustomProperty(CLE_MODE, mode)
    couche.setCustomProperty(CLE_CHAMP, nomChamp)
    _marquerProjet()


def effacerPreference(couche) -> None:
    """Retire le figement enregistre sur la couche."""
    couche = _coucheProjet(couche)
    if couche is None:
        return
    mode = str(couche.customProperty(CLE_MODE, "") or "").strip()
    champ = str(couche.customProperty(CLE_CHAMP, "") or "").strip()
    if not mode and not champ:
        return
    couche.removeCustomProperty(CLE_MODE)
    couche.removeCustomProperty(CLE_CHAMP)
    _marquerProjet()


def _copierOrdreVisuel(vueSource, vueCible) -> None:
    source = vueSource.horizontalHeader()
    cible = vueCible.horizontalHeader()
    if source.count() != cible.count():
        return
    for visuel in range(source.count()):
        logique = source.logicalIndex(visuel)
        actuel = cible.visualIndex(logique)
        if actuel < 0 or actuel == visuel:
            continue
        cible.moveSection(actuel, visuel)


class FigementColonnes:
    """Garde des colonnes visibles pendant le defilement horizontal."""

    def __init__(self, vue):
        self.vue = vue
        self.vueFigee = None
        self.colonnesFigees = []
        self.largeurs = {}
        self.actif = False
        self.occupation = False
        self.synchro = False
        self.abandon = False
        self.enCours = False
        self.liens = []
        self.suivi = None
        self.rappel = None
        self.modeCourant = ""
        self.champCourant = ""
        self.indiceCourant = -1

    def definirSuivi(self, suivi) -> None:
        """Recoit l'indice logique quand l'utilisateur clique une colonne figee."""
        self.suivi = suivi

    def definirRappel(self, rappel) -> None:
        """Recoit True quand un figement est pose, False quand il est retire."""
        self.rappel = rappel

    def estActif(self) -> bool:
        return self.actif and self.vueFigee is not None

    def appliquer(self, indiceCible: int, mode: str) -> str:
        """Fige selon le mode. Retourne un message si l'action est refusee."""
        if self.enCours:
            return ""
        if estSupprime(self.vue) or self.vue.model() is None:
            return traduire("La table n'est plus disponible.")
        if mode not in MODES:
            return traduire("Mode de figement inconnu.")
        try:
            indiceCible = int(indiceCible)
        except (TypeError, ValueError):
            return traduire("Choisissez une colonne à figer.")
        self.enCours = True
        try:
            return self._appliquer(indiceCible, mode)
        finally:
            self.enCours = False

    def _appliquer(self, indiceCible: int, mode: str) -> str:
        self.liberer()
        reparerLargeursNulles(self.vue)
        indices = listerColonnesVisibles(self.vue)
        if indiceCible not in indices:
            return traduire("Cliquez sur l'en-tête d'une colonne de champ.")
        parts = repartirColonnes(indices, indiceCible, mode)
        if parts is None:
            return traduire("Laissez au moins une colonne défilante.")
        figees, _defilantes = parts
        separateur = self._trouverSeparateur()
        if separateur is None:
            return traduire("Cette table ne permet pas de figer des colonnes.")
        self.modeCourant = mode
        self.champCourant = nomChampColonne(self.vue, indiceCible)
        self.indiceCourant = indiceCible
        try:
            self._monter(separateur, figees, mode)
        except Exception:
            self.liberer()
            raise
        self.actif = True
        self._notifier(True)
        self._memoriserProjet(indiceCible, mode)
        return ""

    def abandonner(self) -> None:
        """La table se ferme : rendre les colonnes sans les figer a nouveau."""
        self.abandon = True
        self.liberer()

    def liberer(self) -> None:
        """Retire le figement et rend les colonnes a la table."""
        if self.occupation:
            return
        if not self.actif and self.vueFigee is None and not self.largeurs:
            return
        self.occupation = True
        self.actif = False
        try:
            self._delier()
            self._restaurerColonnes()
            self._retirerVue()
        finally:
            self.colonnesFigees = []
            self.largeurs = {}
            self.occupation = False
            self._notifier(False)

    def _memoriserProjet(self, indice: int, mode: str) -> None:
        try:
            nom = self.champCourant or nomChampColonne(self.vue, indice)
            if not nom:
                tracerErreur(
                    "Enregistrement du projet",
                    RuntimeError("Le champ de la colonne figee est introuvable."),
                )
                return
            self.champCourant = nom
            enregistrerPreference(coucheDeLaVue(self.vue), mode, nom)
        except Exception as erreur:
            tracerErreur("Enregistrement du projet", erreur)

    def _notifier(self, actif: bool) -> None:
        if self.rappel is None:
            return
        try:
            self.rappel(actif)
        except Exception as erreur:
            tracerErreur("Rappel du figement", erreur)

    def _trouverSeparateur(self):
        parent = self.vue.parent() if not estSupprime(self.vue) else None
        while parent is not None and not estSupprime(parent):
            if isinstance(parent, QSplitter):
                return parent
            parent = parent.parent()
        return None

    def _monter(self, separateur, figees, mode) -> None:
        self.largeurs = {
            indice: max(24, self.vue.columnWidth(indice)) for indice in figees
        }
        self.colonnesFigees = list(figees)
        vueFigee = QTableView()
        vueFigee.setObjectName("pincolumnsVueFigee")
        vueFigee.setFrameShape(QFrame.NoFrame)
        vueFigee.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        vueFigee.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        vueFigee.setVerticalScrollMode(self.vue.verticalScrollMode())
        vueFigee.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        vueFigee.setAlternatingRowColors(self.vue.alternatingRowColors())
        vueFigee.setShowGrid(self.vue.showGrid())
        vueFigee.setWordWrap(self.vue.wordWrap())
        vueFigee.setFont(self.vue.font())
        vueFigee.setPalette(self.vue.palette())
        vueFigee.setSelectionBehavior(self.vue.selectionBehavior())
        vueFigee.setSelectionMode(self.vue.selectionMode())
        vueFigee.setEditTriggers(self.vue.editTriggers())
        vueFigee.setSortingEnabled(False)
        vueFigee.setFocusPolicy(Qt.StrongFocus)
        self._copierHauteurLignes(vueFigee)
        vueFigee.setModel(self.vue.model())
        selection = self.vue.selectionModel()
        if selection is not None:
            vueFigee.setSelectionModel(selection)
        self._poserDelegue(vueFigee, selection)
        self._copierHauteurLignes(vueFigee)
        _copierOrdreVisuel(self.vue, vueFigee)
        self._montrerSeulement(vueFigee, figees)
        vueFigee.verticalHeader().hide()
        entete = vueFigee.horizontalHeader()
        entete.setStretchLastSection(False)
        entete.setHighlightSections(False)
        entete.setSectionResizeMode(QHeaderView.Interactive)
        self.vueFigee = vueFigee
        self._inserer(separateur, vueFigee, mode)
        # Sans ce blocage, QGIS enregistre une largeur 0 sur la couche.
        self._modifierVueSansMemoire(
            lambda: [self.vue.setColumnHidden(indice, True) for indice in figees]
        )
        self._brancher()
        self._ajusterLargeur()
        self._alignerEntetes()
        self._synchroniserHauteurs(True)
        self._depuisPrincipale(self.vue.verticalScrollBar().value())
        self._majIndicateurTri()
        vueFigee.show()

    def _poserDelegue(self, vueFigee, selection) -> None:
        delegue = QgsAttributeTableDelegate(vueFigee)
        if selection is not None:
            try:
                modeleSelection = sip.cast(selection, QgsFeatureSelectionModel)
                if modeleSelection is not None:
                    delegue.setFeatureSelectionModel(modeleSelection)
            except Exception as erreur:
                tracerErreur("Selection de la vue figee", erreur)
        vueFigee.setItemDelegate(delegue)

    def _copierHauteurLignes(self, vueFigee) -> None:
        source = self.vue.verticalHeader()
        cible = vueFigee.verticalHeader()
        cible.setDefaultSectionSize(source.defaultSectionSize())
        cible.setMinimumSectionSize(source.minimumSectionSize())

    def _montrerSeulement(self, vueFigee, figees) -> None:
        ensemble = set(figees)
        entete = self.vue.horizontalHeader()
        for visuel in range(entete.count()):
            logique = entete.logicalIndex(visuel)
            if logique < 0:
                continue
            if logique in ensemble:
                vueFigee.setColumnHidden(logique, False)
                vueFigee.setColumnWidth(logique, self.largeurs.get(logique, 80))
            else:
                vueFigee.setColumnHidden(logique, True)

    def _inserer(self, separateur, vueFigee, mode) -> None:
        indexTable = separateur.indexOf(self.vue)
        if indexTable < 0:
            raise RuntimeError("La table n'est pas dans le separateur.")
        indexInsertion = indexTable + 1 if mode == MODE_APRES else indexTable
        separateur.insertWidget(indexInsertion, vueFigee)
        separateur.setStretchFactor(separateur.indexOf(vueFigee), 0)
        separateur.setStretchFactor(separateur.indexOf(self.vue), 1)
        self._ajusterLargeur()
        self._fixerTailles(separateur)

    def _fixerTailles(self, separateur) -> None:
        if self.vueFigee is None:
            return
        tailles = separateur.sizes()
        for index in range(separateur.count()):
            enfant = separateur.widget(index)
            if enfant is self.vueFigee:
                tailles[index] = self.vueFigee.width()
            elif enfant is not self.vue and not enfant.isVisible():
                tailles[index] = 0
        separateur.setSizes(tailles)

    def _largeurVoulue(self) -> int:
        if self.vueFigee is None:
            return 0
        total = self.vueFigee.frameWidth() * 2
        for indice in self.colonnesFigees:
            total += max(24, self.vueFigee.columnWidth(indice))
        return max(total, 48)

    def _ajusterLargeur(self) -> None:
        if self.vueFigee is None or estSupprime(self.vueFigee):
            return
        largeur = self._largeurVoulue()
        self.vueFigee.setFixedWidth(largeur)

    def _alignerEntetes(self) -> None:
        if self.occupation or self.vueFigee is None or estSupprime(self.vue):
            return
        hauteur = self.vue.horizontalHeader().height()
        if hauteur <= 0:
            return
        entete = self.vueFigee.horizontalHeader()
        if entete.height() != hauteur:
            entete.setFixedHeight(hauteur)

    def _brancher(self) -> None:
        enteteFigee = self.vueFigee.horizontalHeader()
        self._lier(enteteFigee.sectionClicked, self._surEnteteFigee)
        self._lier(self.vueFigee.clicked, self._surCelluleFigee)
        self._lier(enteteFigee.sectionResized, self._surLargeurFigee)
        self._lier(self.vue.horizontalHeader().sectionResized, self._surLargeurPrincipale)
        self._lier(self.vue.horizontalHeader().geometriesChanged, self._alignerEntetes)
        self._lier(self.vue.horizontalHeader().sortIndicatorChanged, self._surTriPrincipal)
        self._lier(self.vue.verticalHeader().sectionResized, self._surHauteurLigne)
        self._lier(self.vue.verticalScrollBar().valueChanged, self._depuisPrincipale)
        self._lier(self.vueFigee.verticalScrollBar().valueChanged, self._depuisFigee)
        modele = self.vue.model()
        if modele is not None:
            self._lier(modele.modelReset, self._retirerApresCoup)
            self._lier(modele.columnsAboutToBeRemoved, self._retirerApresCoup)
        selection = self.vue.selectionModel()
        if selection is not None:
            self._lier(selection.selectionChanged, self._rafraichir)
            self._suivreRepeint(selection)

    def _lier(self, signal, slot) -> None:
        signal.connect(slot)
        self.liens.append((signal, slot))

    def _delier(self) -> None:
        for signal, slot in self.liens:
            try:
                signal.disconnect(slot)
            except Exception as erreur:
                tracerRepli("Deconnexion d'un signal", erreur)
        self.liens = []

    def _modifierVueSansMemoire(self, action) -> None:
        """Change la vue sans laisser QGIS memoriser une largeur nulle."""
        if estSupprime(self.vue):
            return
        self.vue.blockSignals(True)
        try:
            action()
        finally:
            if not estSupprime(self.vue):
                self.vue.blockSignals(False)

    def _restaurerColonnes(self) -> None:
        if estSupprime(self.vue):
            return
        largeurs = dict(self.largeurs)
        self._modifierVueSansMemoire(
            lambda: [
                self.vue.setColumnHidden(indice, False) for indice in largeurs
            ]
        )
        for indice, largeur in largeurs.items():
            if largeur > 0 and not estSupprime(self.vue):
                self.vue.setColumnWidth(indice, largeur)

    def _retirerVue(self) -> None:
        vueFigee = self.vueFigee
        self.vueFigee = None
        if vueFigee is None or estSupprime(vueFigee):
            return
        vueFigee.hide()
        vueFigee.setParent(None)
        vueFigee.deleteLater()

    def _retirerApresCoup(self, *_args) -> None:
        if self.occupation or not self.actif or self.abandon:
            return
        QTimer.singleShot(0, self._reposer)

    def _reposer(self) -> None:
        """Repose le figement apres un rechargement de la table."""
        if self.abandon or self.occupation or estSupprime(self.vue):
            return
        mode, champ = lirePreference(coucheDeLaVue(self.vue))
        if mode not in MODES or not champ:
            mode = self.modeCourant
            champ = self.champCourant
        if mode not in MODES or not champ:
            return
        indice = indiceColonneChamp(self.vue, champ)
        if indice < 0:
            indice = self.indiceCourant
        if indice < 0:
            return
        try:
            self.appliquer(indice, mode)
        except Exception as erreur:
            tracerErreur("Repose du figement", erreur)

    def _surEnteteFigee(self, indice: int) -> None:
        self._annoncer(indice)
        self._trier(indice)

    def _surCelluleFigee(self, index) -> None:
        if index is None or not index.isValid():
            return
        self._annoncer(index.column())

    def _annoncer(self, indice: int) -> None:
        if self.suivi is None or indice < 0:
            return
        try:
            self.suivi(int(indice))
        except Exception as erreur:
            tracerErreur("Suivi de colonne", erreur)

    def _trier(self, indice: int) -> None:
        if self.occupation or estSupprime(self.vue) or indice < 0:
            return
        entete = self.vue.horizontalHeader()
        ordre = Qt.AscendingOrder
        if (
            entete.sortIndicatorSection() == indice
            and entete.sortIndicatorOrder() == Qt.AscendingOrder
        ):
            ordre = Qt.DescendingOrder
        self.vue.sortByColumn(indice, ordre)

    def _surTriPrincipal(self, _indice, _ordre) -> None:
        self._majIndicateurTri()

    def _majIndicateurTri(self) -> None:
        if self.vueFigee is None or estSupprime(self.vue) or self.occupation:
            return
        entete = self.vue.horizontalHeader()
        section = entete.sortIndicatorSection()
        cible = self.vueFigee.horizontalHeader()
        if section not in self.colonnesFigees:
            cible.setSortIndicatorShown(False)
            return
        self.occupation = True
        try:
            cible.setSortIndicator(section, entete.sortIndicatorOrder())
            cible.setSortIndicatorShown(True)
        finally:
            self.occupation = False

    def _surLargeurFigee(self, indice, _ancienne, nouvelle) -> None:
        if self.occupation or indice not in self.colonnesFigees:
            return
        self.occupation = True
        try:
            self.largeurs[indice] = nouvelle
            if not estSupprime(self.vue):
                self._modifierVueSansMemoire(
                    lambda indiceColonne=indice, largeur=nouvelle: self.vue.setColumnWidth(
                        indiceColonne, largeur
                    )
                )
            self._ajusterLargeur()
        finally:
            self.occupation = False

    def _surLargeurPrincipale(self, indice, _ancienne, nouvelle) -> None:
        if self.occupation or self.vueFigee is None or indice not in self.colonnesFigees:
            return
        self.occupation = True
        try:
            self.largeurs[indice] = nouvelle
            self.vueFigee.setColumnWidth(indice, nouvelle)
            self._ajusterLargeur()
        finally:
            self.occupation = False

    def _surHauteurLigne(self, indice, _ancienne, nouvelle) -> None:
        if self.vueFigee is None or estSupprime(self.vueFigee) or nouvelle <= 0:
            return
        if self.vueFigee.rowHeight(indice) != nouvelle:
            self.vueFigee.setRowHeight(indice, nouvelle)

    def _depuisPrincipale(self, valeur) -> None:
        if self.synchro or self.vueFigee is None or estSupprime(self.vueFigee):
            return
        self.synchro = True
        try:
            self.vueFigee.verticalScrollBar().setValue(valeur)
            self._synchroniserHauteurs(False)
        finally:
            self.synchro = False

    def _depuisFigee(self, valeur) -> None:
        if self.synchro or estSupprime(self.vue):
            return
        self.synchro = True
        try:
            self.vue.verticalScrollBar().setValue(valeur)
        finally:
            self.synchro = False

    def _hauteursUniformes(self) -> bool:
        modele = self.vue.model()
        if modele is None:
            return True
        defaut = self.vue.verticalHeader().defaultSectionSize()
        nombre = min(modele.rowCount(), 30)
        for ligne in range(nombre):
            if self.vue.rowHeight(ligne) != defaut:
                return False
        return True

    def _synchroniserHauteurs(self, complet: bool) -> None:
        if self.vueFigee is None or estSupprime(self.vue) or self._hauteursUniformes():
            return
        modele = self.vue.model()
        if modele is None:
            return
        nombre = modele.rowCount()
        if complet and 0 < nombre <= _HAUTEUR_MAX_SYNCHRO:
            debut, fin = 0, nombre - 1
        else:
            debut = self.vue.rowAt(0)
            if debut < 0:
                return
            fin = self.vue.rowAt(max(0, self.vue.viewport().height() - 1))
            if fin < 0:
                fin = min(nombre - 1, debut + 80)
        for ligne in range(max(0, debut), fin + 1):
            hauteur = self.vue.rowHeight(ligne)
            if hauteur > 0 and self.vueFigee.rowHeight(ligne) != hauteur:
                self.vueFigee.setRowHeight(ligne, hauteur)

    def _suivreRepeint(self, selection) -> None:
        """QGIS repeint la table via requestRepaint, pas via selectionChanged.

        Le clic sur le numero de ligne passe par ce signal. Sans lui, la
        vue figee garde l'ancienne couleur jusqu'au prochain clic.
        """
        try:
            modele = sip.cast(selection, QgsFeatureSelectionModel)
        except Exception as erreur:
            tracerRepli("Modele de selection", erreur)
            return
        if modele is None:
            return
        try:
            self._lier(modele.requestRepaint["QModelIndexList"], self._rafraichir)
            self._lier(modele.requestRepaint[()], self._rafraichir)
        except Exception as erreur:
            tracerErreur("Suivi du repeint", erreur)

    def _rafraichir(self, *_args) -> None:
        if self.vueFigee is not None and not estSupprime(self.vueFigee):
            self.vueFigee.viewport().update()
