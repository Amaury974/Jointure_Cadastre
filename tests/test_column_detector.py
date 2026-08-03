# -*- coding: utf-8 -*-
import unittest

from core.column_detector import detecter_roles_colonnes


class TestDetecterRolesColonnes(unittest.TestCase):

    def test_detection_basique_mode_combine(self):
        echantillon = {
            "commune": ["SAINT PIERRE", "SAINT LEU", "SAINT PAUL"],
            "parcelle": ["AB0012", "CD 0034", "EF 0056"],
            "autre_colonne": ["x", "y", "z"],
        }
        config = detecter_roles_colonnes(echantillon)
        self.assertEqual(config["mode"], "section_numero_ensemble")
        self.assertEqual(config["colonne_commune"], "commune")
        self.assertEqual(config["colonne_parcelle_combinee"], "parcelle")

    def test_detection_colonnes_separees(self):
        echantillon = {
            "commune": ["SAINT PIERRE", "SAINT LEU", "SAINT PAUL"],
            "section": ["AB", "CD", "EF"],
            "numero": ["0012", "0034", "0056"],
        }
        config = detecter_roles_colonnes(echantillon)
        self.assertEqual(config["mode"], "colonnes_separees")
        self.assertEqual(config["colonne_section"], "section")
        self.assertEqual(config["colonne_numero"], "numero")

    def test_colonne_date_exclue_grace_au_nom_entete(self):
        """
        Régression (cas réel observé) : une colonne "Date du paiement"
        contenant des valeurs qui, une fois restituées sous forme de texte
        par le lecteur GDAL/OGR (ex: "08/28/25"), ressemblent par coïncidence
        à des fragments de numéro de parcelle valides — au point d'obtenir un
        meilleur score de CONTENU que la vraie colonne de parcelles. Le nom
        de la colonne suffit à elle seul à écarter ce cas, sans même avoir
        besoin d'information de type de champ.
        """
        echantillon = {
            "Code postal et Commune": [
                "97480 - Saint-Joseph", "97412 - Bras-Panon", "97442 - Saint-Philippe",
                "97427 - L'Étang-Salé", "97480 - Saint-Joseph",
            ] + [""] * 20,
            "N° de parcelle(s)": ["CO#0049", "AL 0060", "AZ 0025", "AD 123", "BL 0675"] + [""] * 20,  # 4/5 = 0.8
            "Date du paiement ": (
                ["08/28/25", "08/27/25", "08/01/25", "08/27/25", "08/27/25"] + ["12/30/99"] * 20
            ),  # 25/25 = 1.0 (score de contenu supérieur, mais nom de colonne explicite)
        }

        config = detecter_roles_colonnes(echantillon)
        self.assertEqual(config["colonne_parcelle_combinee"], "N° de parcelle(s)")
        self.assertEqual(config["colonne_commune"], "Code postal et Commune")

    def test_colonne_montant_exclue_meme_sans_mot_cle_parcelle_ailleurs(self):
        """Une colonne 'Montant de la subvention (€)' ne doit jamais être choisie, quel que soit son contenu."""
        echantillon = {
            "commune": ["SAINT PIERRE", "SAINT LEU", "SAINT PAUL"],
            "identifiant parcelle": ["AB0012", "CD 0034", "EF 0056"],
            "Montant de la subvention (€)": ["1200", "3400", "5600"],  # contenu numérique, pourrait matcher "numero"
        }
        config = detecter_roles_colonnes(echantillon)
        self.assertNotEqual(config["colonne_parcelle_combinee"], "Montant de la subvention (€)")
        self.assertEqual(config["colonne_parcelle_combinee"], "identifiant parcelle")

    def test_repli_sur_contenu_si_entetes_non_explicites(self):
        """Sans mot-clé reconnaissable dans les en-têtes, la détection retombe sur le contenu comme avant."""
        echantillon = {
            "colA": ["SAINT PIERRE", "SAINT LEU", "SAINT PAUL"],
            "colB": ["AB0012", "CD 0034", "EF 0056"],
        }
        config = detecter_roles_colonnes(echantillon)
        self.assertEqual(config["colonne_commune"], "colA")
        self.assertEqual(config["colonne_parcelle_combinee"], "colB")

    def test_types_colonnes_toujours_pris_en_compte_en_complement(self):
        """Le filtrage par type reste actif pour les colonnes sans en-tête explicite ni exclusion par mot-clé."""
        echantillon = {
            "colA": ["SAINT PIERRE", "SAINT LEU", "SAINT PAUL"],
            "colB": ["AB0012", "CD 0034", "EF 0056"],
            "colC": ["12/30/99", "12/30/99", "12/30/99"],  # pas de mot-clé d'exclusion, mais type non-texte
        }
        types_colonnes = {"colA": "texte", "colB": "texte", "colC": "autre"}
        config = detecter_roles_colonnes(echantillon, types_colonnes=types_colonnes)
        self.assertEqual(config["colonne_parcelle_combinee"], "colB")


if __name__ == "__main__":
    unittest.main()
