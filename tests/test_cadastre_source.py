# -*- coding: utf-8 -*-
import unittest

from core.cadastre_source import departement_depuis_insee, url_commune


class TestCadastreSourceUrl(unittest.TestCase):

    def test_departement_reunion(self):
        self.assertEqual(departement_depuis_insee("97411"), "974")
        self.assertEqual(departement_depuis_insee("97410"), "974")

    def test_departement_metropole(self):
        self.assertEqual(departement_depuis_insee("75056"), "75")
        self.assertEqual(departement_depuis_insee("01001"), "01")

    def test_departement_corse(self):
        self.assertEqual(departement_depuis_insee("2A004"), "2A")
        self.assertEqual(departement_depuis_insee("2B033"), "2B")

    def test_url_commune_reunion(self):
        url = url_commune("97411")
        self.assertEqual(
            url,
            "https://cadastre.data.gouv.fr/data/etalab-cadastre/latest/geojson/"
            "communes/974/97411/cadastre-97411-parcelles.json.gz",
        )

    def test_url_commune_autre_source(self):
        url = url_commune("97411", source="batiments")
        self.assertTrue(url.endswith("cadastre-97411-batiments.json.gz"))


if __name__ == "__main__":
    unittest.main()
