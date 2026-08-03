# -*- coding: utf-8 -*-
import unittest

from core.ftp_loader import _lister_fichiers_associes


class FakeFTP:
    def __init__(self, fichiers):
        self._fichiers = fichiers

    def nlst(self, dossier):
        return self._fichiers


class TestListerFichiersAssocies(unittest.TestCase):

    def test_selectionne_uniquement_le_bon_nom_de_base(self):
        ftp = FakeFTP([
            "/dossier/Cadastre.shp",
            "/dossier/Cadastre.shx",
            "/dossier/Cadastre.dbf",
            "/dossier/Cadastre.prj",
            "/dossier/AutreCouche.shp",
            "/dossier/AutreCouche.dbf",
        ])
        fichiers = _lister_fichiers_associes(ftp, "/dossier", "Cadastre")
        noms = sorted(f.split("/")[-1] for f in fichiers)
        self.assertEqual(noms, ["Cadastre.dbf", "Cadastre.prj", "Cadastre.shp", "Cadastre.shx"])

    def test_ignore_extensions_non_shapefile(self):
        ftp = FakeFTP([
            "/dossier/Cadastre.shp",
            "/dossier/Cadastre.xml",
            "/dossier/Cadastre.txt",
        ])
        fichiers = _lister_fichiers_associes(ftp, "/dossier", "Cadastre")
        noms = sorted(f.split("/")[-1] for f in fichiers)
        self.assertEqual(noms, ["Cadastre.shp"])

    def test_insensible_a_la_casse(self):
        ftp = FakeFTP(["/dossier/CADASTRE.SHP", "/dossier/cadastre.dbf"])
        fichiers = _lister_fichiers_associes(ftp, "/dossier", "Cadastre")
        self.assertEqual(len(fichiers), 2)

    def test_aucun_fichier_trouve(self):
        ftp = FakeFTP(["/dossier/Autre.shp"])
        fichiers = _lister_fichiers_associes(ftp, "/dossier", "Cadastre")
        self.assertEqual(fichiers, [])


if __name__ == "__main__":
    unittest.main()
