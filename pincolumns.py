# -*- coding: utf-8 -*-
"""Ajoute le bouton de figement dans chaque table attributaire."""

import os

from qgis.PyQt import sip
from qgis.PyQt.QtCore import QEvent, QObject, QTimer, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAction,
    QActionGroup,
    QApplication,
    QMenu,
    QToolBar,
    QToolButton,
)
from qgis.core import Qgis

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
    reparerLargeursNulles,
    tracerErreur,
)
from .textes import traduire

_ESSAIS_MAX = 8


def _libelles() -> dict:
    return {
        MODE_AVANT: traduire("Figer cette colonne et celles d'avant"),
        MODE_SEULE: traduire("Figer seulement cette colonne"),
        MODE_APRES: traduire("Figer les colonnes d'après"),
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
        vue.clicked.connect(lambda index, v=vue: self._memoriser(v, index.column()))

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
        if estSupprime(etat.actionLiberer):
            return
        etat.actionLiberer.setEnabled(bool(actif))

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
        except Exception:
            pass
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
