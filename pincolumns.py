# -*- coding: utf-8 -*-
"""Ajoute le bouton de figement dans chaque table attributaire."""

import os

from qgis.PyQt import sip
from qgis.PyQt.QtCore import (
    QCoreApplication,
    QEvent,
    QItemSelectionModel,
    QMetaObject,
    QObject,
    QPoint,
    QTimer,
    Qt,
)
from qgis.PyQt.QtGui import QIcon, QKeySequence
from qgis.PyQt.QtWidgets import (
    QAction,
    QActionGroup,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QInputDialog,
    QMenu,
    QToolBar,
    QToolButton,
)
from qgis.core import QgsExpressionContext, QgsExpressionContextUtils, Qgis
from qgis.gui import QgsDualView, QgsExpressionBuilderWidget

from .figer_colonnes import (
    MODE_APRES,
    MODE_AVANT,
    MODE_SEULE,
    MODES,
    FigementColonnes,
    coucheDeLaVue,
    effacerPreference,
    estSupprime,
    indiceColonneChamp,
    lirePreference,
    listerColonnesVisibles,
    reparerLargeursNulles,
    tracerErreur,
    tracerRepli,
)
from .textes import traduire

_ESSAIS_MAX = 8


def _libelles() -> dict:
    return {
        MODE_AVANT: traduire("Figer cette colonne et celles d'avant"),
        MODE_SEULE: traduire("Figer seulement cette colonne"),
        MODE_APRES: traduire("Figer cette colonne et celles d'après"),
    }


def _infos() -> dict:
    return {
        MODE_AVANT: traduire(
            "Cette colonne et celles d'avant restent à gauche. Les suivantes défilent."
        ),
        MODE_SEULE: traduire(
            "Seule cette colonne reste à gauche. Les colonnes d'avant et d'après défilent."
        ),
        MODE_APRES: traduire(
            "Cette colonne et celles d'après restent à droite. Les précédentes défilent."
        ),
    }


def _texteQgis(contexte: str, source: str) -> str:
    """Reprend le libelle de QGIS, dans la langue de l'interface."""
    return QCoreApplication.translate(contexte, source)


def _nomClasse(obj) -> str:
    """Nom C++ de l'objet. isinstance echoue souvent dans un filtre d'evenements."""
    if obj is None or estSupprime(obj):
        return ""
    try:
        meta = obj.metaObject()
    except Exception:
        return ""
    if meta is None:
        return ""
    return meta.className() or ""


def _estDialogueTable(obj) -> bool:
    if obj is None or estSupprime(obj):
        return False
    if _nomClasse(obj) == "QgsAttributeTableDialog":
        return True
    try:
        nom = obj.objectName() or ""
    except Exception:
        return False
    return nom.startswith("QgsAttributeTableDialog")


def creerIcone() -> QIcon:
    """Charge icon.png place a cote du plugin."""
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
    if not os.path.isfile(chemin):
        return QIcon()
    return QIcon(chemin)


class _EtatDialogue:
    """Bouton et figement attaches a une table ouverte."""

    def __init__(self, dialogue):
        self.dialogue = dialogue
        self.bouton = None
        self.separation = None
        self.actionDefaut = None
        self.actionsModes = {}
        self.actionLiberer = None
        self.figement = None


class SurveillantTables(QObject):
    """Pose le bouton des qu'une table attributaire apparait."""

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.fenetre = iface.mainWindow()
        self.etats = {}
        self.icone = self._icone()
        self.enRestauration = False
        self.minuteur = QTimer(self)
        self.minuteur.setInterval(400)
        self.minuteur.timeout.connect(self.balayer)

    def demarrer(self) -> None:
        """Surveille les tables deja ouvertes et celles qui s'ouvrent ensuite."""
        self.balayer()
        if not self.minuteur.isActive():
            self.minuteur.start()

    def arreter(self) -> None:
        self.minuteur.stop()

    def examinerFenetresOuvertes(self) -> None:
        """Ajoute le bouton aux tables deja ouvertes."""
        self.balayer()

    def balayer(self) -> None:
        """Cherche les tables dans les fenetres ouvertes.

        QGIS montre la table dans un QDialog ordinaire. Le widget
        QgsAttributeTableDialog est a l'interieur.
        """
        application = QApplication.instance()
        if application is None:
            return
        for fenetre in application.topLevelWidgets():
            classe = _nomClasse(fenetre)
            if "Dialog" not in classe and "Dock" not in classe:
                continue
            self._chercherTable(fenetre)

    def retirerTout(self) -> None:
        """Enleve les boutons et libere les colonnes."""
        for cle in list(self.etats.keys()):
            self._retirerEtat(cle)

    def eventFilter(self, obj, event):
        try:
            if event.type() == QEvent.ContextMenu and self._gererClicDroitFigee(obj, event):
                return True
            if event.type() == QEvent.Show and _estDialogueTable(obj):
                QTimer.singleShot(0, lambda o=obj: self.installer(o))
            elif event.type() == QEvent.Show and _nomClasse(obj) in (
                "QDialog",
                "QgsNonRejectableDialog",
                "QgsDockWidget",
            ):
                QTimer.singleShot(0, lambda o=obj: self._chercherTable(o))
            elif event.type() == QEvent.ChildAdded and obj is self.fenetre:
                enfant = event.child()
                if _estDialogueTable(enfant):
                    QTimer.singleShot(0, lambda o=enfant: self.installer(o))
        except Exception as erreur:
            tracerErreur("Filtre des tables", erreur)
        return False

    def _chercherTable(self, racine) -> None:
        if estSupprime(racine):
            return
        if _estDialogueTable(racine):
            self.installer(racine)
            return
        try:
            enfants = racine.findChildren(QObject)
        except Exception:
            return
        for enfant in enfants:
            if _estDialogueTable(enfant):
                self.installer(enfant)

    def installer(self, dialogue, essai: int = 0) -> None:
        """Ajoute le bouton a menu sur la barre de la table."""
        if estSupprime(dialogue) or not _estDialogueTable(dialogue):
            return
        if dialogue.property("pincolumnsPret"):
            return
        if essai == 0 and dialogue.property("pincolumnsEnCours"):
            return
        dialogue.setProperty("pincolumnsEnCours", True)
        barre = self._trouverBarre(dialogue)
        vue = self._trouverVue(dialogue)
        if barre is None or vue is None:
            if essai < _ESSAIS_MAX:
                QTimer.singleShot(150, lambda d=dialogue, n=essai + 1: self.installer(d, n))
            else:
                dialogue.setProperty("pincolumnsEnCours", False)
                tracerErreur(
                    "Bouton de table",
                    RuntimeError("Barre ou vue introuvable."),
                )
            return
        existant = barre.findChild(QToolButton, "pincolumnsBouton")
        if existant is not None:
            existant.setObjectName("pincolumnsBoutonAncien")
            existant.hide()
            existant.deleteLater()
        try:
            etat = self._poserBouton(dialogue, barre, vue)
        except Exception as erreur:
            dialogue.setProperty("pincolumnsEnCours", False)
            tracerErreur("Installation du bouton", erreur)
            return
        dialogue.setProperty("pincolumnsPret", True)
        dialogue.setProperty("pincolumnsMode", MODE_AVANT)
        cle = id(dialogue)
        self.etats[cle] = etat
        dialogue.destroyed.connect(lambda _objet=None, c=cle: self._oublier(c))
        dialogue.finished.connect(lambda _code=0, c=cle: self._relacher(c))
        try:
            self._suivreColonne(vue)
        except Exception as erreur:
            tracerErreur("Suivi de la colonne", erreur)
        QTimer.singleShot(0, lambda d=dialogue, v=vue, e=etat: self._restaurer(d, v, e))

    def _poserBouton(self, dialogue, barre, vue) -> _EtatDialogue:
        etat = _EtatDialogue(dialogue)
        bouton = QToolButton(barre)
        bouton.setObjectName("pincolumnsBouton")
        bouton.setPopupMode(QToolButton.MenuButtonPopup)
        bouton.setToolButtonStyle(Qt.ToolButtonIconOnly)
        bouton.setAutoRaise(True)
        bouton.setIcon(self.icone)
        bouton.setIconSize(barre.iconSize())
        menu = QMenu(bouton)
        groupe = QActionGroup(menu)
        groupe.setExclusive(True)
        libelles = _libelles()
        infos = _infos()
        for mode in (MODE_AVANT, MODE_SEULE, MODE_APRES):
            action = QAction(libelles[mode], menu)
            action.setCheckable(True)
            action.setToolTip(infos[mode])
            action.setData(mode)
            if mode == MODE_AVANT:
                action.setChecked(True)
            groupe.addAction(action)
            menu.addAction(action)
            action.triggered.connect(
                lambda coche, m=mode, d=dialogue: self._choisirMode(d, m, coche)
            )
            etat.actionsModes[mode] = action
        menu.addSeparator()
        actionLiberer = QAction(traduire("Libérer les colonnes"), menu)
        actionLiberer.setEnabled(False)
        actionLiberer.triggered.connect(lambda _coche=False, d=dialogue: self._liberer(d))
        menu.addAction(actionLiberer)
        court = traduire("Figer les colonnes")
        actionDefaut = QAction(self.icone, court, bouton)
        actionDefaut.setToolTip(court)
        actionDefaut.triggered.connect(lambda _coche=False, d=dialogue: self._executer(d))
        bouton.setDefaultAction(actionDefaut)
        bouton.setMenu(menu)
        bouton.setPopupMode(QToolButton.MenuButtonPopup)
        bouton.setToolTip(court)
        etat.bouton = bouton
        etat.actionDefaut = actionDefaut
        etat.actionLiberer = actionLiberer
        etat.separation = barre.addSeparator()
        barre.addWidget(bouton)
        etat.figement = FigementColonnes(vue)
        etat.figement.definirSuivi(lambda indice, v=vue: self._memoriser(v, indice))
        etat.figement.definirRappel(lambda actif, e=etat: self._marquerActif(e, actif))
        return etat

    def _choisirMode(self, dialogue, mode: str, coche: bool) -> None:
        if self.enRestauration or not coche or estSupprime(dialogue):
            return
        dialogue.setProperty("pincolumnsMode", mode)
        etat = self.etats.get(id(dialogue))
        if etat is not None:
            self._mettreAJourInfo(etat, mode)
        self._executer(dialogue)

    def _executer(self, dialogue) -> None:
        if estSupprime(dialogue):
            return
        try:
            vue = self._trouverVue(dialogue)
            if vue is None:
                self._prevenir(traduire("La table attributaire est introuvable."), Qgis.Warning)
                return
            indice = vue.property("pincolumnsColonne")
            if indice is None:
                self._prevenir(
                    traduire("Cliquez sur l'en-tête de la colonne à figer."),
                    Qgis.Warning,
                )
                return
            mode = dialogue.property("pincolumnsMode") or MODE_AVANT
            etat = self.etats.get(id(dialogue))
            if etat is None or etat.figement is None:
                self._prevenir(traduire("Le bouton n'est plus lié à cette table."), Qgis.Warning)
                return
            message = etat.figement.appliquer(indice, str(mode))
            if message:
                self._prevenir(message, Qgis.Warning)
                return
            self._cocherMode(etat, str(mode))
        except Exception as erreur:
            tracerErreur("Figement des colonnes", erreur)
            self._prevenir(
                traduire("Le figement a échoué. Le détail est dans le journal PinColumns."),
                Qgis.Critical,
            )

    def _liberer(self, dialogue) -> None:
        if estSupprime(dialogue):
            return
        etat = self.etats.get(id(dialogue))
        if etat is None or etat.figement is None:
            return
        try:
            vue = self._trouverVue(dialogue)
            etat.figement.liberer()
            effacerPreference(coucheDeLaVue(vue))
            self._decocherModes(etat)
        except Exception as erreur:
            tracerErreur("Liberation des colonnes", erreur)
            self._prevenir(
                traduire("Les colonnes n'ont pas pu être libérées."),
                Qgis.Critical,
            )

    def _suivreColonne(self, vue) -> None:
        if vue.property("pincolumnsSuivi"):
            return
        vue.setProperty("pincolumnsSuivi", True)
        entete = vue.horizontalHeader()
        if entete is not None:
            entete.sectionClicked.connect(lambda indice, v=vue: self._memoriser(v, indice))
            # Apres le slot de QGIS, qui cree le menu puis appelle popup().
            entete.customContextMenuRequested.connect(
                lambda pos, v=vue: self._completerMenuEntete(v, pos),
                Qt.QueuedConnection,
            )
        vue.clicked.connect(lambda index, v=vue: self._memoriser(v, index.column()))

    def _completerMenuEntete(self, vue, point: QPoint) -> None:
        """Ajoute le figement au menu contextuel de l'en-tete, apres celui de QGIS."""
        try:
            if self.enRestauration or estSupprime(vue):
                return
            dialogue = self._dialoguePourVue(vue)
            if dialogue is None or estSupprime(dialogue):
                return
            entete = vue.horizontalHeader()
            if entete is None or estSupprime(entete):
                return
            indice = entete.logicalIndexAt(point)
            if indice < 0:
                return
            dual = self._trouverDualView(vue)
            if dual is None:
                tracerRepli("Menu entete", RuntimeError("QgsDualView introuvable."))
                return
            menuQgis = self._menuEnteteQgis(dual)
            if menuQgis is None:
                tracerRepli("Menu entete", RuntimeError("Menu horizontal introuvable."))
                return
            etat = self.etats.get(id(dialogue))
            self._poserSousMenuFigement(menuQgis, etat, vue, indice)
        except Exception as erreur:
            tracerErreur("Menu entete des colonnes", erreur)

    def _poserSousMenuFigement(self, menuParent, etat, vue, indice: int) -> None:
        """Ajoute le sous-menu de figement. La vue est la table principale."""
        if estSupprime(menuParent) or etat is None or etat.figement is None:
            return
        dialogue = etat.dialogue
        if estSupprime(dialogue) or estSupprime(vue):
            return
        if menuParent.findChild(QObject, "pincolumnsMenuEntete") is not None:
            return
        menuParent.addSeparator()
        sousMenu = QMenu(traduire("Figer les colonnes"), menuParent)
        sousMenu.setObjectName("pincolumnsMenuEntete")
        groupe = QActionGroup(sousMenu)
        groupe.setExclusive(True)
        libelles = _libelles()
        infos = _infos()
        colMemorisee = vue.property("pincolumnsColonne")
        figementActif = etat.figement.estActif()
        modeCourant = dialogue.property("pincolumnsMode") or MODE_AVANT
        cocher = False
        if figementActif and colMemorisee is not None:
            try:
                cocher = int(colMemorisee) == indice
            except (TypeError, ValueError):
                cocher = False
        for mode in (MODE_AVANT, MODE_SEULE, MODE_APRES):
            action = QAction(libelles[mode], sousMenu)
            action.setCheckable(True)
            action.setToolTip(infos[mode])
            action.setData(mode)
            if cocher and mode == modeCourant:
                action.setChecked(True)
            groupe.addAction(action)
            sousMenu.addAction(action)
            action.triggered.connect(
                lambda coche, m=mode, d=dialogue, v=vue, i=indice: self._figerDepuisEntete(
                    d, v, i, m, coche
                )
            )
        sousMenu.addSeparator()
        actionLiberer = QAction(traduire("Libérer les colonnes"), sousMenu)
        actionLiberer.setEnabled(figementActif)
        actionLiberer.triggered.connect(lambda _coche=False, d=dialogue: self._liberer(d))
        sousMenu.addAction(actionLiberer)
        menuParent.addMenu(sousMenu)

    def _figerDepuisEntete(self, dialogue, vue, indice, mode: str, coche: bool) -> None:
        if not coche:
            return
        self._memoriser(vue, indice)
        self._choisirMode(dialogue, mode, True)

    def _brancherMenusFiges(self, etat) -> None:
        """Le clic droit de la vue figee n'existe pas : QGIS ne connait que la table principale."""
        figement = etat.figement if etat is not None else None
        if figement is None or estSupprime(figement.vueFigee):
            return
        vueFigee = figement.vueFigee
        if vueFigee.property("pincolumnsMenus"):
            return
        vueFigee.setProperty("pincolumnsMenus", True)
        try:
            viewport = vueFigee.viewport()
            if viewport is not None:
                viewport.installEventFilter(self)
            entete = vueFigee.horizontalHeader()
            if entete is not None:
                entete.setContextMenuPolicy(Qt.CustomContextMenu)
                entete.customContextMenuRequested.connect(
                    lambda pos, e=etat, v=vueFigee: self._menuEnteteFigee(e, v, pos)
                )
        except Exception as erreur:
            tracerErreur("Menus de la vue figee", erreur)

    def _gererClicDroitFigee(self, obj, event) -> bool:
        if obj is None or estSupprime(obj):
            return False
        vueFigee = obj.parent()
        if estSupprime(vueFigee) or _nomClasse(vueFigee) == "":
            return False
        try:
            if vueFigee.objectName() != "pincolumnsVueFigee":
                return False
        except Exception:
            return False
        self._menuCelluleFigee(vueFigee, event.pos(), event.globalPos())
        return True

    def _menuCelluleFigee(self, vueFigee, pos, posGlobale) -> None:
        """Meme menu de cellule que la table QGIS, pour la ligne et la colonne cliquees."""
        try:
            if estSupprime(vueFigee):
                return
            index = vueFigee.indexAt(pos)
            if index is None or not index.isValid():
                return
            etat = self._etatPourVueFigee(vueFigee)
            if etat is None or etat.figement is None or estSupprime(etat.figement.vue):
                return
            vue = etat.figement.vue
            selection = vue.selectionModel()
            if selection is not None:
                selection.setCurrentIndex(index, QItemSelectionModel.NoUpdate)
            menu = QMenu(vueFigee)
            actionTout = menu.addAction(_texteQgis("QgsAttributeTableView", "Select All"))
            actionTout.setShortcut(QKeySequence.SelectAll)
            actionTout.triggered.connect(lambda _coche=False, v=vue: v.selectAll())
            maitre = index
            modele = vue.model()
            if modele is not None and hasattr(modele, "mapToMaster"):
                try:
                    maitre = modele.mapToMaster(index)
                except Exception as erreur:
                    tracerRepli("Index maitre de la cellule", erreur)
            if hasattr(vue, "willShowContextMenu"):
                vue.willShowContextMenu.emit(menu, maitre)
            if menu.actions():
                menu.popup(posGlobale)
        except Exception as erreur:
            tracerErreur("Menu cellule de la vue figee", erreur)

    def _menuEnteteFigee(self, etat, vueFigee, point: QPoint) -> None:
        """Meme menu d'en-tete que QGIS, plus le figement, sur la colonne figee."""
        try:
            if self.enRestauration or estSupprime(vueFigee) or etat is None or etat.figement is None:
                return
            vue = etat.figement.vue
            if estSupprime(vue):
                return
            entete = vueFigee.horizontalHeader()
            if entete is None or estSupprime(entete):
                return
            indice = entete.logicalIndexAt(point)
            if indice < 0:
                return
            menu = QMenu(vueFigee)
            self._ajouterActionsEntete(menu, etat, indice)
            self._poserSousMenuFigement(menu, etat, vue, indice)
            if menu.actions():
                menu.popup(entete.mapToGlobal(point))
        except Exception as erreur:
            tracerErreur("Menu entete de la vue figee", erreur)

    def _ajouterActionsEntete(self, menu, etat, indice: int) -> None:
        dual = self._dualPour(etat.figement.vue)
        if dual is None:
            return
        actions = (
            ("&Hide Column", lambda _coche=False, i=indice, e=etat: self._masquerColonne(e, i)),
            ("&Set Width…", lambda _coche=False, i=indice, e=etat: self._demanderLargeur(e, i, False)),
            (
                "&Set All Column Widths…",
                lambda _coche=False, i=indice, e=etat: self._demanderLargeur(e, i, True),
            ),
            ("&Autosize", lambda _coche=False, i=indice, e=etat: self._ajusterColonnes(e, i, False)),
            (
                "&Autosize All Columns",
                lambda _coche=False, i=indice, e=etat: self._ajusterColonnes(e, i, True),
            ),
        )
        for source, slot in actions:
            action = QAction(_texteQgis("QgsDualView", source), menu)
            action.triggered.connect(slot)
            menu.addAction(action)
        menu.addSeparator()
        organiser = QAction(_texteQgis("QgsDualView", "&Organize Columns…"), menu)
        organiser.triggered.connect(lambda _coche=False, d=dual: self._organiserColonnes(d))
        menu.addAction(organiser)
        trier = QAction(_texteQgis("QgsDualView", "&Sort…"), menu)
        trier.triggered.connect(lambda _coche=False, d=dual, e=etat: self._ouvrirTri(e, d))
        menu.addAction(trier)

    def _etatPourVueFigee(self, vueFigee):
        for etat in self.etats.values():
            figement = etat.figement
            if figement is None or estSupprime(figement.vueFigee):
                continue
            if figement.vueFigee is vueFigee:
                return etat
        return None

    def _dualPour(self, vue):
        parent = self._trouverDualView(vue)
        if parent is None:
            return None
        try:
            dual = sip.cast(parent, QgsDualView)
        except Exception as erreur:
            tracerRepli("Lecture du dual view", erreur)
            return None
        return dual

    def _masquerColonne(self, etat, indice: int) -> None:
        try:
            dual = self._dualPour(etat.figement.vue)
            if dual is None:
                return
            config = dual.attributeTableConfig()
            source = config.mapVisibleColumnToIndex(int(indice))
            if source < 0:
                return
            config.setColumnHidden(source, True)
            dual.setAttributeTableConfig(config)
        except Exception as erreur:
            tracerErreur("Masquage d'une colonne figee", erreur)

    def _demanderLargeur(self, etat, indice: int, toutes: bool) -> None:
        try:
            figement = etat.figement
            if figement is None or estSupprime(figement.vue):
                return
            actuelle = self._largeurVisible(figement, indice)
            if toutes:
                titre = _texteQgis("QgsDualView", "Set Column Width")
                minimum = 1
            else:
                titre = _texteQgis("QgsDualView", "Set column width")
                minimum = 0
            valeur, ok = QInputDialog.getInt(
                figement.vue,
                titre,
                _texteQgis("QgsDualView", "Enter column width"),
                max(actuelle, minimum),
                minimum,
                1000,
                10,
            )
            if not ok:
                return
            self._ecrireLargeurs(etat, valeur, None if toutes else indice)
        except Exception as erreur:
            tracerErreur("Largeur d'une colonne figee", erreur)

    def _ajusterColonnes(self, etat, indice: int, toutes: bool) -> None:
        try:
            figement = etat.figement
            if figement is None or estSupprime(figement.vue):
                return
            if toutes:
                self._ajusterAuContenu(figement.vue, listerColonnesVisibles(figement.vue))
                if not estSupprime(figement.vueFigee):
                    self._ajusterAuContenu(figement.vueFigee, list(figement.colonnesFigees))
                self._ecrireLargeurs(etat, None, None)
                return
            vue = figement.vue
            if indice in figement.colonnesFigees and not estSupprime(figement.vueFigee):
                vue = figement.vueFigee
            self._ajusterAuContenu(vue, [indice])
            self._ecrireLargeurs(etat, None, indice)
        except Exception as erreur:
            tracerErreur("Ajustement d'une colonne figee", erreur)

    def _ajusterAuContenu(self, vue, indices) -> None:
        if estSupprime(vue):
            return
        entete = vue.horizontalHeader()
        if entete is not None:
            entete.blockSignals(True)
        try:
            for indice in indices:
                vue.resizeColumnToContents(int(indice))
        finally:
            if entete is not None and not estSupprime(entete):
                entete.blockSignals(False)

    def _ecrireLargeurs(self, etat, valeur, indiceSeul) -> None:
        figement = etat.figement
        dual = self._dualPour(figement.vue)
        if dual is None or estSupprime(figement.vue):
            return
        config = dual.attributeTableConfig()
        if valeur is not None and indiceSeul is None:
            nombre = figement.vue.model().columnCount() if figement.vue.model() else 0
            for colonne in range(nombre):
                config.setColumnWidth(colonne, int(valeur))
        else:
            entete = figement.vue.horizontalHeader()
            cibles = [indiceSeul] if indiceSeul is not None else [
                entete.logicalIndex(visuel) for visuel in range(entete.count())
            ]
            for logique in cibles:
                if logique < 0:
                    continue
                largeur = int(valeur) if valeur is not None else self._largeurVisible(figement, logique)
                if largeur <= 0:
                    continue
                source = config.mapVisibleColumnToIndex(int(logique))
                if source < 0:
                    continue
                config.setColumnWidth(source, largeur)
        figement.occupation = True
        try:
            dual.setAttributeTableConfig(config)
        finally:
            figement.occupation = False
        self._reporterLargeurs(figement, valeur, indiceSeul)

    def _reporterLargeurs(self, figement, valeur, indiceSeul) -> None:
        if estSupprime(figement.vueFigee) or estSupprime(figement.vue):
            return
        for indice in figement.colonnesFigees:
            if valeur is not None and (indiceSeul is None or indiceSeul == indice):
                largeur = int(valeur)
            else:
                largeur = self._largeurVisible(figement, indice)
            if largeur > 0 and figement.vueFigee.columnWidth(indice) != largeur:
                figement.vueFigee.setColumnWidth(indice, largeur)
        try:
            figement._ajusterLargeur()
        except Exception as erreur:
            tracerRepli("Largeur de la vue figee", erreur)

    def _largeurVisible(self, figement, logique: int) -> int:
        if (
            logique in figement.colonnesFigees
            and not estSupprime(figement.vueFigee)
        ):
            return figement.vueFigee.columnWidth(logique)
        if estSupprime(figement.vue):
            return 0
        return figement.vue.columnWidth(logique)

    def _organiserColonnes(self, dual) -> None:
        try:
            QMetaObject.invokeMethod(dual, "organizeColumns", Qt.DirectConnection)
        except Exception as erreur:
            tracerErreur("Organisation des colonnes", erreur)

    def _ouvrirTri(self, etat, dual) -> None:
        """Reprend le dialogue de tri de QGIS, qui n'est pas exposé au Python."""
        try:
            if dual is None or dual.masterModel() is None:
                return
            couche = dual.masterModel().layer()
            if couche is None:
                return
            dialogue = QDialog(etat.dialogue)
            dialogue.setWindowTitle(
                _texteQgis("QgsDualView", "Configure Attribute Table Sort Order")
            )
            boutons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            disposition = QGridLayout(dialogue)
            boutons.accepted.connect(dialogue.accept)
            boutons.rejected.connect(dialogue.reject)
            groupe = QGroupBox(
                _texteQgis("QgsDualView", "Defined sort order in attribute table")
            )
            groupe.setCheckable(True)
            expression = dual.sortExpression() or ""
            groupe.setChecked(bool(expression))
            disposition.addWidget(groupe)
            grille = QGridLayout(groupe)
            constructeur = QgsExpressionBuilderWidget(groupe)
            contexte = QgsExpressionContext(
                QgsExpressionContextUtils.globalProjectLayerScopes(couche)
            )
            constructeur.initWithLayer(couche, contexte, "generic")
            constructeur.setExpressionText(expression or couche.displayExpression())
            grille.addWidget(constructeur)
            ascendant = QCheckBox(_texteQgis("QgsDualView", "Sort ascending"))
            config = dual.attributeTableConfig()
            ascendant.setChecked(config.sortOrder() == Qt.AscendingOrder)
            grille.addWidget(ascendant)
            disposition.addWidget(boutons)
            if dialogue.exec_() != QDialog.Accepted:
                return
            ordre = Qt.AscendingOrder if ascendant.isChecked() else Qt.DescendingOrder
            if groupe.isChecked():
                texte = constructeur.expressionText()
                dual.setSortExpression(texte, ordre)
                config.setSortExpression(texte)
                config.setSortOrder(ordre)
            else:
                dual.setSortExpression("", ordre)
                config.setSortExpression("")
            figement = etat.figement
            if figement is not None:
                figement.occupation = True
            try:
                dual.setAttributeTableConfig(config)
            finally:
                if figement is not None:
                    figement.occupation = False
        except Exception as erreur:
            tracerErreur("Tri de la table", erreur)

    def _dialoguePourVue(self, vue):
        for etat in self.etats.values():
            figement = etat.figement
            if figement is None:
                continue
            if estSupprime(figement.vue):
                continue
            if figement.vue is vue:
                return etat.dialogue
        for etat in self.etats.values():
            dialogue = etat.dialogue
            if estSupprime(dialogue):
                continue
            candidate = self._trouverVue(dialogue)
            if candidate is vue:
                return dialogue
        return None

    def _trouverDualView(self, vue):
        parent = vue.parent()
        while parent is not None and not estSupprime(parent):
            if _nomClasse(parent) == "QgsDualView":
                return parent
            parent = parent.parent()
        return None

    def _menuEnteteQgis(self, dual):
        """Menu d'en-tete que QGIS vient de creer, enfant direct du dual view."""
        try:
            dernier = None
            for enfant in dual.children():
                if estSupprime(enfant) or _nomClasse(enfant) != "QMenu":
                    continue
                menu = sip.cast(enfant, QMenu)
                if menu is None:
                    continue
                dernier = menu
                if menu.isVisible():
                    return menu
            return dernier
        except Exception as erreur:
            tracerRepli("Menu entete", erreur)
        return None

    def _memoriser(self, vue, indice) -> None:
        if estSupprime(vue):
            return
        try:
            indice = int(indice)
        except (TypeError, ValueError):
            return
        if indice < 0:
            return
        vue.setProperty("pincolumnsColonne", indice)

    def _cocherMode(self, etat, mode: str) -> None:
        """Une seule action du menu reste cochee."""
        for candidat, action in etat.actionsModes.items():
            if estSupprime(action):
                continue
            if candidat == mode:
                action.setChecked(True)
        for candidat, action in etat.actionsModes.items():
            if estSupprime(action) or candidat == mode:
                continue
            if action.isChecked():
                action.setChecked(False)

    def _decocherModes(self, etat) -> None:
        """Aucune action de figement ne reste cochee."""
        for action in etat.actionsModes.values():
            if estSupprime(action) or not action.isChecked():
                continue
            action.setChecked(False)

    def _figementTient(self, etat) -> bool:
        """Vrai si les colonnes figees sont encore masquees dans la table principale."""
        figement = etat.figement if etat is not None else None
        if figement is None or not figement.estActif() or figement.abandon:
            return False
        vue = figement.vue
        if estSupprime(vue) or not figement.colonnesFigees:
            return False
        try:
            return all(vue.isColumnHidden(indice) for indice in figement.colonnesFigees)
        except Exception:
            return False

    def _restaurer(self, dialogue, vue, etat) -> None:
        """Repose le figement enregistre sur la couche."""
        if estSupprime(dialogue) or estSupprime(vue) or etat is None or etat.figement is None:
            return
        if self._figementTient(etat) or self.enRestauration or etat.figement.enCours:
            return
        self.enRestauration = True
        try:
            reparerLargeursNulles(vue)
            mode, champ = lirePreference(coucheDeLaVue(vue))
            if mode not in MODES or not champ:
                return
            indice = indiceColonneChamp(vue, champ)
            if indice < 0:
                return
            self._memoriser(vue, indice)
            dialogue.setProperty("pincolumnsMode", mode)
            self._cocherMode(etat, mode)
            self._mettreAJourInfo(etat, mode)
            message = etat.figement.appliquer(indice, mode)
            if message:
                tracerErreur("Restauration", RuntimeError(message))
        except Exception as erreur:
            tracerErreur("Restauration du figement", erreur)
        finally:
            self.enRestauration = False

    def _mettreAJourInfo(self, etat, mode: str) -> None:
        """L'infobulle du bouton reste courte, quel que soit le mode."""
        if mode not in MODES or estSupprime(etat.actionDefaut):
            return
        court = traduire("Figer les colonnes")
        etat.actionDefaut.setText(court)
        etat.actionDefaut.setToolTip(court)
        if not estSupprime(etat.bouton):
            etat.bouton.setToolTip(court)

    def _marquerActif(self, etat, actif: bool) -> None:
        if not estSupprime(etat.actionLiberer):
            etat.actionLiberer.setEnabled(bool(actif))
        if actif:
            self._brancherMenusFiges(etat)

    def _trouverBarre(self, dialogue):
        trouvees = []
        for enfant in dialogue.findChildren(QObject):
            if _nomClasse(enfant) != "QToolBar" or estSupprime(enfant):
                continue
            barre = sip.cast(enfant, QToolBar)
            if barre is None:
                continue
            if barre.objectName() == "mToolbar":
                return barre
            trouvees.append(barre)
        return trouvees[0] if trouvees else None

    def _trouverVue(self, dialogue):
        try:
            from qgis.gui import QgsDualView
        except Exception as erreur:
            tracerErreur("Import de la vue double", erreur)
            return None
        for enfant in dialogue.findChildren(QObject):
            if _nomClasse(enfant) != "QgsDualView" or estSupprime(enfant):
                continue
            try:
                dual = sip.cast(enfant, QgsDualView)
                if dual is None:
                    continue
                return dual.tableView()
            except Exception as erreur:
                tracerErreur("Lecture de la table", erreur)
                return None
        return None

    def _prevenir(self, texte: str, niveau) -> None:
        try:
            barre = self.iface.messageBar()
            if barre is not None:
                barre.pushMessage("PinColumns", texte, niveau, 6)
        except Exception as erreur:
            tracerErreur("Message PinColumns", erreur)

    def _icone(self) -> QIcon:
        icone = creerIcone()
        if icone.isNull():
            tracerErreur("Icone", FileNotFoundError("icon.png introuvable."))
        return icone

    def _relacher(self, cle: int) -> None:
        """La table se ferme : rendre les colonnes, garder la preference."""
        etat = self.etats.get(cle)
        if etat is None or etat.figement is None:
            return
        try:
            etat.figement.abandonner()
        except Exception as erreur:
            tracerErreur("Fermeture de la table", erreur)

    def _oublier(self, cle: int) -> None:
        """La table est detruite : ne plus retenir le figement."""
        etat = self.etats.pop(cle, None)
        if etat is None or etat.figement is None:
            return
        try:
            etat.figement._delier()
        except Exception as erreur:
            tracerRepli("Oubli des signaux", erreur)
        etat.figement.actif = False
        etat.figement.vueFigee = None
        etat.figement = None

    def _retirerEtat(self, cle: int) -> None:
        etat = self.etats.pop(cle, None)
        if etat is None:
            return
        try:
            if etat.figement is not None:
                etat.figement.liberer()
        except Exception as erreur:
            tracerErreur("Retrait du figement", erreur)
        dialogue = etat.dialogue
        if not estSupprime(dialogue):
            dialogue.setProperty("pincolumnsPret", False)
        self._retirerBouton(etat)

    def _retirerBouton(self, etat) -> None:
        bouton = etat.bouton
        if estSupprime(bouton):
            return
        barre = bouton.parent()
        if isinstance(barre, QToolBar):
            for action in list(barre.actions()):
                if barre.widgetForAction(action) is bouton:
                    barre.removeAction(action)
                    break
            if etat.separation is not None:
                barre.removeAction(etat.separation)
        bouton.deleteLater()


class PinColumns:
    """Point d'entree du plugin."""

    def __init__(self, iface):
        """Conserve l'interface QGIS.

        :param iface: interface QGIS
        :type iface: QgsInterface
        """
        self.iface = iface
        self.surveillant = None

    def initGui(self) -> None:
        """Surveille l'ouverture des tables attributaires."""
        try:
            application = QApplication.instance()
            if application is None:
                return
            self.surveillant = SurveillantTables(self.iface)
            application.installEventFilter(self.surveillant)
            self.surveillant.demarrer()
        except Exception as erreur:
            tracerErreur("Initialisation", erreur)

    def unload(self) -> None:
        """Retire le bouton et libere les colonnes figees."""
        application = QApplication.instance()
        surveillant = self.surveillant
        self.surveillant = None
        if surveillant is None:
            return
        try:
            surveillant.arreter()
            if application is not None:
                application.removeEventFilter(surveillant)
            surveillant.retirerTout()
        except Exception as erreur:
            tracerErreur("Dechargement", erreur)
