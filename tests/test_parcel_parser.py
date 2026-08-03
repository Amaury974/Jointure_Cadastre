# -*- coding: utf-8 -*-
import unittest

from core.parcel_parser import decouper_parcelles


class TestDecouperParcelles(unittest.TestCase):

    def test_parcelle_unique_avec_espace(self):
        r = decouper_parcelles("CO 0049")
        self.assertEqual(r["parcelles"], [("CO", "0049")])
        self.assertFalse(r["multiple"])

    def test_parcelle_unique_sans_espace(self):
        r = decouper_parcelles("AY138")
        self.assertEqual(r["parcelles"], [("AY", "138")])

    def test_plusieurs_parcelles_point_virgule(self):
        r = decouper_parcelles("AM 0497 ; AM 0282 ; AM 0343 ; AM 0375")
        self.assertEqual(len(r["parcelles"]), 4)
        self.assertTrue(r["multiple"])
        self.assertEqual(r["parcelles"][0], ("AM", "0497"))

    def test_plusieurs_parcelles_et(self):
        r = decouper_parcelles("BL 0135 et BL 0381")
        self.assertEqual(r["parcelles"], [("BL", "0135"), ("BL", "0381")])

    def test_section_heritee_slash(self):
        # Seule la 1ere valeur porte la section, les suivantes en héritent
        r = decouper_parcelles("BM 180 / 213 / 104")
        self.assertEqual(r["parcelles"], [("BM", "180"), ("BM", "213"), ("BM", "104")])

    def test_sections_explicites_virgule(self):
        r = decouper_parcelles("AI220, AI219")
        self.assertEqual(r["parcelles"], [("AI", "220"), ("AI", "219")])

    def test_valeur_vide(self):
        r = decouper_parcelles("")
        self.assertEqual(r["parcelles"], [])
        self.assertFalse(r["multiple"])

    def test_guillemets_englobants(self):
        r = decouper_parcelles('"AM 0497 ; AM 0282"')
        self.assertEqual(len(r["parcelles"]), 2)


if __name__ == "__main__":
    unittest.main()
