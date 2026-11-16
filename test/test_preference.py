# -*- coding: utf-8 -*-
"""Tests de la preference de figement enregistree sur la couche."""

import os
import sys
import tempfile
import unittest

from qgis.core import QgsProject, QgsVectorLayer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from figer_colonnes import (
    CLE_CHAMP,
    CLE_MODE,
    MODE_AVANT,
    MODE_SEULE,
    effacerPreference,
    enregistrerPreference,
    lirePreference,
)


def _coucheOrientation():
    return QgsVectorLayer(
        "None?field=id:integer&field=d:string",
        "orientation",
        "memory",
    )


class TestPreference(unittest.TestCase):
    def setUp(self):
        self.projet = QgsProject.instance()
        self.projet.clear()
        self.dossier = tempfile.TemporaryDirectory()
        self.couche = _coucheOrientation()
        self.assertTrue(self.couche.isValid())
        self.projet.addMapLayer(self.couche)
        self.projet.setDirty(False)

    def tearDown(self):
        self.projet.clear()
        self.projet.setDirty(False)
        self.dossier.cleanup()

    def testLitUneCoucheSansPreference(self):
        self.assertEqual(lirePreference(self.couche), ("", ""))
        self.assertEqual(lirePreference(None), ("", ""))

    def testEnregistreEtRelitLeModeEtLeChamp(self):
        enregistrerPreference(self.couche, MODE_SEULE, "d")
        self.assertEqual(lirePreference(self.couche), (MODE_SEULE, "d"))
        self.assertEqual(self.couche.customProperty(CLE_MODE), MODE_SEULE)
        self.assertEqual(self.couche.customProperty(CLE_CHAMP), "d")
        self.assertTrue(self.projet.isDirty())

    def testIgnoreUnModeOuUnChampInvalide(self):
        enregistrerPreference(self.couche, "autre", "d")
        enregistrerPreference(self.couche, MODE_AVANT, "")
        enregistrerPreference(None, MODE_AVANT, "d")
        self.assertEqual(lirePreference(self.couche), ("", ""))

    def testNeReecritPasUnePreferenceIdentique(self):
        enregistrerPreference(self.couche, MODE_SEULE, "d")
        self.projet.setDirty(False)
        enregistrerPreference(self.couche, MODE_SEULE, "d")
        self.assertEqual(lirePreference(self.couche), (MODE_SEULE, "d"))
        self.assertFalse(self.projet.isDirty())

    def testEffaceLaPreference(self):
        enregistrerPreference(self.couche, MODE_SEULE, "d")
        effacerPreference(self.couche)
        self.assertEqual(lirePreference(self.couche), ("", ""))
        self.assertIsNone(self.couche.customProperty(CLE_MODE))
        self.assertIsNone(self.couche.customProperty(CLE_CHAMP))

    def testEffacerSansPreferenceNeChangeRien(self):
        self.projet.setDirty(False)
        effacerPreference(self.couche)
        effacerPreference(None)
        self.assertEqual(lirePreference(self.couche), ("", ""))
        self.assertFalse(self.projet.isDirty())

    def testNalterePasLaVisibiliteDesColonnes(self):
        avant = [
            (colonne.name, colonne.hidden)
            for colonne in self.couche.attributeTableConfig().columns()
        ]
        enregistrerPreference(self.couche, MODE_SEULE, "d")
        apres = [
            (colonne.name, colonne.hidden)
            for colonne in self.couche.attributeTableConfig().columns()
        ]
        self.assertEqual(avant, apres)

    def testSurvitALenregistrementDuProjet(self):
        enregistrerPreference(self.couche, MODE_SEULE, "d")
        chemin = os.path.join(self.dossier.name, "orientation.qgs")
        self.assertTrue(self.projet.write(chemin))
        self.projet.clear()
        self.assertTrue(self.projet.read(chemin))
        couches = self.projet.mapLayersByName("orientation")
        self.assertEqual(len(couches), 1)
        self.assertEqual(lirePreference(couches[0]), (MODE_SEULE, "d"))


if __name__ == "__main__":
    unittest.main()
