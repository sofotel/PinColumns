# -*- coding: utf-8 -*-
"""Les boutons et infobulles existent en francais, anglais et espagnol."""

import os
import re
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from textes import definirLangue, traduire

_DOSSIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SOURCES = ("pincolumns.py", "figer_colonnes.py")


def _messagesDuCode():
    trouves = []
    motif = re.compile(r'traduire\(\s*"([^"]+)"\s*\)')
    for nom in _SOURCES:
        chemin = os.path.join(_DOSSIER, nom)
        with open(chemin, encoding="utf-8") as fichier:
            trouves.extend(motif.findall(fichier.read()))
    return trouves


def _traductions(langue):
    chemin = os.path.join(_DOSSIER, "i18n", f"PinColumns_{langue}.ts")
    racine = ET.parse(chemin).getroot()
    table = {}
    for message in racine.iter("message"):
        source = message.find("source")
        traduction = message.find("translation")
        table[source.text] = traduction.text or ""
    return table


class TestTraduction(unittest.TestCase):
    def tearDown(self):
        definirLangue("")

    def testLeBoutonPrincipalAUneInfobulleCourte(self):
        definirLangue("fr")
        self.assertEqual(traduire("Figer les colonnes"), "Figer les colonnes")
        definirLangue("en")
        self.assertEqual(traduire("Figer les colonnes"), "Freeze columns")
        definirLangue("es")
        self.assertEqual(traduire("Figer les colonnes"), "Fijar las columnas")

    def testLesTroisLanguesCouvrentLesTextesDuCode(self):
        messages = _messagesDuCode()
        self.assertGreaterEqual(len(messages), 8)
        francais = _traductions("fr")
        anglais = _traductions("en")
        espagnol = _traductions("es")
        for message in messages:
            self.assertIn(message, francais)
            self.assertEqual(francais[message], message)
            self.assertTrue(anglais.get(message))
            self.assertNotEqual(anglais[message], message)
            self.assertTrue(espagnol.get(message))
            self.assertNotEqual(espagnol[message], message)

    def testUneLangueInconnueGardeLeFrancais(self):
        definirLangue("de")
        self.assertEqual(traduire("Libérer les colonnes"), "Libérer les colonnes")
