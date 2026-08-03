# -*- coding: utf-8 -*-
"""
Référentiel des communes de La Réunion (département 974).

Ce module est volontairement isolé (pas de dépendance QGIS) et fournit :
    - la liste des 24 communes avec leur code INSEE officiel
    - une liste d'alias de reconnaissance (variantes de saisie fréquentes :
      sans accents, sans tirets, abréviations "St"/"Ste", etc.)

Codes INSEE vérifiés sur https://www.insee.fr/fr/metadonnees/geographie/departement/974-la-reunion
(COG au 1er janvier 2026).

Si ce plugin doit être adapté à un autre département / une autre zone,
il suffit de remplacer ce fichier par un référentiel équivalent — le reste
du code (commune_matcher.py) ne dépend que de la structure ci-dessous.
"""

# Chaque entrée : code_insee, nom_officiel, [alias de reconnaissance en MAJUSCULES SANS ACCENTS]
COMMUNES_REUNION = [
    ("97401", "Les Avirons", ["LES AVIRONS", "AVIRONS"]),
    ("97402", "Bras-Panon", ["BRAS PANON", "BRAS-PANON"]),
    ("97403", "Entre-Deux", ["ENTRE DEUX", "ENTRE-DEUX", "L ENTRE DEUX"]),
    ("97404", "L'Étang-Salé", ["ETANG SALE", "L ETANG SALE", "ETANG-SALE", "L'ETANG-SALE"]),
    ("97405", "Petite-Île", ["PETITE ILE", "PETITE-ILE"]),
    ("97406", "La Plaine-des-Palmistes", [
        "LA PLAINE DES PALMISTES", "PLAINE DES PALMISTES", "PLAINE-DES-PALMISTES",
    ]),
    ("97407", "Le Port", ["LE PORT", "PORT"]),
    ("97408", "La Possession", ["LA POSSESSION", "POSSESSION"]),
    ("97409", "Saint-André", ["SAINT ANDRE", "ST ANDRE", "SAINT-ANDRE"]),
    ("97410", "Saint-Benoît", ["SAINT BENOIT", "ST BENOIT", "SAINT-BENOIT"]),
    ("97411", "Saint-Denis", ["SAINT DENIS", "ST DENIS", "SAINT-DENIS"]),
    ("97412", "Saint-Joseph", ["SAINT JOSEPH", "ST JOSEPH", "SAINT-JOSEPH"]),
    ("97413", "Saint-Leu", ["SAINT LEU", "ST LEU", "SAINT-LEU"]),
    ("97414", "Saint-Louis", ["SAINT LOUIS", "ST LOUIS", "SAINT-LOUIS"]),
    ("97415", "Saint-Paul", ["SAINT PAUL", "ST PAUL", "SAINT-PAUL"]),
    ("97416", "Saint-Pierre", ["SAINT PIERRE", "ST PIERRE", "SAINT-PIERRE"]),
    ("97417", "Saint-Philippe", ["SAINT PHILIPPE", "ST PHILIPPE", "SAINT-PHILIPPE"]),
    ("97418", "Sainte-Marie", ["SAINTE MARIE", "STE MARIE", "SAINTE-MARIE"]),
    ("97419", "Sainte-Rose", ["SAINTE ROSE", "STE ROSE", "SAINTE-ROSE"]),
    ("97420", "Sainte-Suzanne", ["SAINTE SUZANNE", "STE SUZANNE", "SAINTE-SUZANNE"]),
    ("97421", "Salazie", ["SALAZIE"]),
    ("97422", "Le Tampon", ["LE TAMPON", "TAMPON"]),
    ("97423", "Les Trois-Bassins", ["LES TROIS BASSINS", "TROIS BASSINS", "TROIS-BASSINS"]),
    ("97424", "Cilaos", ["CILAOS"]),
]


def construire_index_alias():
    """
    Construit un dictionnaire {alias_normalisé: (code_insee, nom_officiel)}
    couvrant à la fois le nom officiel et tous les alias déclarés.
    """
    from .commune_matcher import normaliser_nom_commune

    index = {}
    for code_insee, nom_officiel, alias in COMMUNES_REUNION:
        toutes_variantes = [nom_officiel] + alias
        for variante in toutes_variantes:
            index[normaliser_nom_commune(variante)] = (code_insee, nom_officiel)
    return index


def construire_index_codes_insee():
    """Construit un dictionnaire {code_insee: nom_officiel}."""
    return {code_insee: nom_officiel for code_insee, nom_officiel, _ in COMMUNES_REUNION}
