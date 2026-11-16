# -*- coding: utf-8 -*-
"""Textes visibles du bouton, selon la langue de QGIS.

Le francais est la langue source. Anglais et espagnol sont dans i18n/.
"""

import html
import os
import re

from qgis.PyQt.QtCore import QLocale, QSettings

_BLOC_TRADUCTION = re.compile(
    r"<source>(.*?)</source>\s*<translation([^>]*)>(.*?)</translation>",
    re.DOTALL,
)

_LANGUES = ("fr", "en", "es")
_langueForcee = ""
_tables = {}


def definirLangue(code: str) -> None:
    """Force une langue. Une chaine vide revient a la langue de QGIS."""
    global _langueForcee, _tables
    _langueForcee = (code or "").strip().lower()[:2]
    _tables = {}


def langueActive() -> str:
    """Code de langue sur deux lettres."""
    if _langueForcee:
        return _langueForcee
    try:
        return _langueQgis()
    except Exception:
        return "fr"


def traduire(message: str) -> str:
    """Retourne le message dans la langue active."""
    if not message:
        return ""
    langue = langueActive()
    if langue == "fr":
        return message
    return _table(langue).get(message, message)


def _langueQgis() -> str:
    reglages = QSettings()
    surcharge = reglages.value("locale/overrideFlag", False)
    if _estVrai(surcharge):
        locale = str(reglages.value("locale/userLocale", "") or "")
    else:
        locale = QLocale.system().name()
    code = locale.replace("-", "_").split("_")[0].lower()
    if code in _LANGUES:
        return code
    return "fr"


def _estVrai(valeur) -> bool:
    if isinstance(valeur, bool):
        return valeur
    return str(valeur).strip().lower() in ("1", "true", "yes")


def _table(langue: str) -> dict:
    if langue in _tables:
        return _tables[langue]
    chemin = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "i18n",
        f"PinColumns_{langue}.ts",
    )
    table = _lireTs(chemin)
    _tables[langue] = table
    return table


def _lireTs(chemin: str) -> dict:
    if not os.path.isfile(chemin):
        return {}
    try:
        with open(chemin, encoding="utf-8") as fichier:
            contenu = fichier.read()
    except OSError:
        return {}
    table = {}
    for source, attributs, traduction in _BLOC_TRADUCTION.findall(contenu):
        if "unfinished" in attributs:
            continue
        texte = html.unescape(traduction).strip()
        if texte:
            table[html.unescape(source).strip()] = texte
    return table
