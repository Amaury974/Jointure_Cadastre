# -*- coding: utf-8 -*-
import unittest

from core.row_expander import preparer_lignes_depuis_features

OPTIONS = {"majuscules": True, "padding": True}


class TestPreparerLignes(unittest.TestCase):

    def test_mode_combine_ligne_simple(self):
        config = {
            "mode": "section_numero_ensemble",
            "colonne_commune": "commune",
            "colonne_parcelle_combinee": "parcelle",
            "colonne_section": None,
            "colonne_numero": None,
        }
        lignes = [{"commune": "SAINT BENOIT", "parcelle": "CI0148"}]
        resultats = preparer_lignes_depuis_features(lignes, config, OPTIONS)
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]["code_insee"], "97410")
        self.assertEqual(resultats[0]["code_parcelle_normalise"], "97410000CI0148")
        self.assertEqual(resultats[0]["avertissements"], [])

    def test_mode_combine_duplique_lignes_multiples(self):
        config = {
            "mode": "section_numero_ensemble",
            "colonne_commune": "commune",
            "colonne_parcelle_combinee": "parcelle",
            "colonne_section": None,
            "colonne_numero": None,
        }
        lignes = [{"commune": "SAINT ANDRE", "parcelle": "AW787 / AW774"}]
        resultats = preparer_lignes_depuis_features(lignes, config, OPTIONS)
        self.assertEqual(len(resultats), 2)
        self.assertTrue(any("dupliquée" in a for r in resultats for a in r["avertissements"]))
        # Les 2 lignes issues de la duplication pointent vers la même ligne source
        self.assertEqual(resultats[0]["index_ligne_source"], resultats[1]["index_ligne_source"])

    def test_commune_non_reconnue_signalee(self):
        config = {
            "mode": "section_numero_ensemble",
            "colonne_commune": "commune",
            "colonne_parcelle_combinee": "parcelle",
            "colonne_section": None,
            "colonne_numero": None,
        }
        lignes = [{"commune": "VILLE INCONNUE", "parcelle": "AB0001"}]
        resultats = preparer_lignes_depuis_features(lignes, config, OPTIONS)
        self.assertIsNone(resultats[0]["code_insee"])
        self.assertTrue(any("non reconnue" in a for a in resultats[0]["avertissements"]))

    def test_mode_colonnes_separees(self):
        config = {
            "mode": "colonnes_separees",
            "colonne_commune": "commune",
            "colonne_parcelle_combinee": None,
            "colonne_section": "section",
            "colonne_numero": "numero",
        }
        lignes = [{"commune": "SAINT PAUL", "section": "AB", "numero": "12"}]
        resultats = preparer_lignes_depuis_features(lignes, config, OPTIONS)
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]["section"], "AB")
        self.assertEqual(resultats[0]["numero"], "12")


if __name__ == "__main__":
    unittest.main()
