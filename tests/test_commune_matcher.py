# -*- coding: utf-8 -*-
import unittest

from core.commune_matcher import identifier_commune


class TestIdentifierCommune(unittest.TestCase):

    def test_format_code_postal_nom(self):
        r = identifier_commune("97480 - Saint-Joseph")
        self.assertEqual(r["code_insee"], "97412")
        self.assertEqual(r["methode"], "exact")

    def test_nom_seul_sans_accent(self):
        r = identifier_commune("SAINT BENOIT")
        self.assertEqual(r["code_insee"], "97410")

    def test_nom_avec_espace_parasite(self):
        r = identifier_commune(" SAINT LEU")
        self.assertEqual(r["code_insee"], "97413")

    def test_etang_sale_sans_apostrophe(self):
        r = identifier_commune("ETANG SALE")
        self.assertEqual(r["code_insee"], "97404")

    def test_plaine_des_palmistes(self):
        r = identifier_commune("LA PLAINE DES PALMISTES")
        self.assertEqual(r["code_insee"], "97406")

    def test_commune_non_reconnue(self):
        r = identifier_commune("VILLE INEXISTANTE XYZ")
        self.assertIsNone(r["code_insee"])
        self.assertEqual(r["methode"], "non_reconnu")

    def test_valeur_vide(self):
        r = identifier_commune("")
        self.assertIsNone(r["code_insee"])

    def test_code_insee_seul_chaine(self):
        r = identifier_commune("97411")
        self.assertEqual(r["code_insee"], "97411")
        self.assertEqual(r["nom_officiel"], "Saint-Denis")
        self.assertEqual(r["methode"], "code_insee")

    def test_code_insee_seul_entier(self):
        r = identifier_commune(97419)
        self.assertEqual(r["code_insee"], "97419")
        self.assertEqual(r["methode"], "code_insee")

    def test_code_insee_seul_flottant_excel(self):
        # Un tableur exporte parfois une colonne numérique en float ("97416.0")
        r = identifier_commune("97416.0")
        self.assertEqual(r["code_insee"], "97416")
        self.assertEqual(r["methode"], "code_insee")

    def test_code_postal_non_confondu_avec_code_insee(self):
        # 97400 est un code postal réel mais n'est le code INSEE d'aucune commune
        r = identifier_commune("97400")
        self.assertIsNone(r["code_insee"])

    def test_code_insee_invalide(self):
        r = identifier_commune("12345")
        self.assertIsNone(r["code_insee"])


if __name__ == "__main__":
    unittest.main()
