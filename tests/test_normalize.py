# -*- coding: utf-8 -*-
"""
Tests unitaires pour core/normalize.py
Ce fichier ne dépend pas de QGIS et peut être lancé avec un simple :
    python -m unittest tests/test_normalize.py
(à condition d'ajuster le sys.path, ou en le plaçant dans un dossier tests/
 avec un __init__.py adapté)
"""
import unittest

from core.normalize import normaliser_parcelle


class TestNormaliserParcelle(unittest.TestCase):

    def test_format_complet_espaces(self):
        # section d'une seule lettre -> paddée en "0A" (convention cadastrale)
        self.assertEqual(
            normaliser_parcelle("12345 000 A 12"),
            "123450000A0012",
        )

    def test_format_avec_tirets(self):
        self.assertEqual(
            normaliser_parcelle("12345-000-A-12"),
            "123450000A0012",
        )

    def test_section_minuscule(self):
        self.assertEqual(
            normaliser_parcelle("12345 000 a 12", majuscules=True),
            "123450000A0012",
        )

    def test_prefixe_absent(self):
        self.assertEqual(
            normaliser_parcelle("12345 A 12"),
            "123450000A0012",
        )

    def test_valeur_vide(self):
        self.assertEqual(normaliser_parcelle(""), "")
        self.assertEqual(normaliser_parcelle(None), "")

    def test_format_non_reconnu(self):
        # ne doit pas planter : renvoie une version nettoyée
        resultat = normaliser_parcelle("???")
        self.assertIsInstance(resultat, str)


if __name__ == "__main__":
    unittest.main()
