# -*- coding: utf-8 -*-
"""Tests du partage entre colonnes figees et colonnes defilantes."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from figer_colonnes import MODE_APRES, MODE_AVANT, MODE_SEULE, repartirColonnes


class TestRepartition(unittest.TestCase):
    def testAvantGardeLaColonneEtCellesDeGauche(self):
        resultat = repartirColonnes([4, 1, 7, 2], 7, MODE_AVANT)
        self.assertEqual(resultat, ([4, 1, 7], [2]))

    def testSeuleNeFigeQueLaColonneChoisie(self):
        resultat = repartirColonnes([4, 1, 7, 2], 7, MODE_SEULE)
        self.assertEqual(resultat, ([7], [4, 1, 2]))

    def testApresGardeLaColonneEtCellesDeDroite(self):
        resultat = repartirColonnes([4, 1, 7, 2], 7, MODE_APRES)
        self.assertEqual(resultat, ([7, 2], [4, 1]))

    def testRefuseSiToutSeraitFige(self):
        self.assertIsNone(repartirColonnes([3, 8], 8, MODE_AVANT))
        self.assertIsNone(repartirColonnes([3, 8], 3, MODE_APRES))

    def testRefuseUneColonneInconnueOuUnModeInconnu(self):
        self.assertIsNone(repartirColonnes([1, 2, 3], 9, MODE_SEULE))
        self.assertIsNone(repartirColonnes([1, 2, 3], 2, "autre"))
        self.assertIsNone(repartirColonnes([], 0, MODE_AVANT))


if __name__ == "__main__":
    unittest.main()
