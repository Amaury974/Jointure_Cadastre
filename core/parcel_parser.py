# -*- coding: utf-8 -*-
"""
Découpage d'une cellule "numéro de parcelle(s)" en une liste de parcelles
individuelles (section, numéro).

Gère notamment :
    - plusieurs parcelles séparées par ";", ",", "/", "&" ou " et "
    - le cas où seule la première parcelle d'une série porte la lettre de
      section, les suivantes n'étant que des numéros qui héritent de la
      dernière section rencontrée (ex: "BM 180 / 213 / 104" -> BM180, BM213,
      BM104)
    - les espaces/variantes de saisie entre la section et le numéro
      ("CO 0049", "AY138", "AD 123")

Ce module ne dépend pas de QGIS et peut être testé isolément.
"""
import re

# Un "token" de parcelle : lettre(s) de section optionnelles + chiffres
_PATTERN_TOKEN = re.compile(r"^\s*(?P<section>[A-Za-z]{1,2})?\s*(?P<numero>\d+)\s*$")

# Séparateurs reconnus entre plusieurs parcelles sur une même cellule
_PATTERN_SEPARATEURS = re.compile(r"\s*(?:;|,|/|&|\bet\b)\s*", re.IGNORECASE)


def decouper_parcelles(valeur_brute):
    """
    Découpe une valeur brute de cellule en une liste de parcelles.

    :param valeur_brute: la chaîne telle que saisie (peut contenir 1 ou N parcelles)
    :return: dict avec :
        - "parcelles": liste de tuples (section, numero) — tous deux des chaînes,
          `section` peut être "" si non résolue (cas non parsable)
        - "fragments_bruts": liste des fragments de texte originaux (avant
          normalisation), alignée 1-pour-1 avec "parcelles" — utile pour
          l'affichage d'un aperçu "valeur d'origine -> résultat"
        - "multiple": bool, True si plus d'une parcelle a été détectée
        - "tokens_non_reconnus": liste des fragments qui n'ont pas pu être interprétés
    """
    if valeur_brute is None:
        return {"parcelles": [], "fragments_bruts": [], "multiple": False, "tokens_non_reconnus": []}

    texte = str(valeur_brute).strip()
    # Retire des guillemets englobants éventuels (cas CSV: "AM 0497 ; AM 0282")
    if len(texte) >= 2 and texte[0] == '"' and texte[-1] == '"':
        texte = texte[1:-1].strip()

    if not texte:
        return {"parcelles": [], "fragments_bruts": [], "multiple": False, "tokens_non_reconnus": []}

    fragments = [f for f in _PATTERN_SEPARATEURS.split(texte) if f.strip()]

    parcelles = []
    fragments_bruts = []
    tokens_non_reconnus = []
    derniere_section = ""

    for fragment in fragments:
        match = _PATTERN_TOKEN.match(fragment)
        if not match:
            tokens_non_reconnus.append(fragment)
            continue

        section = match.group("section") or ""
        numero = match.group("numero")

        if section:
            derniere_section = section.upper()
        else:
            section = derniere_section  # héritage de la section précédente

        parcelles.append((section, numero))
        fragments_bruts.append(fragment.strip())

    return {
        "parcelles": parcelles,
        "fragments_bruts": fragments_bruts,
        "multiple": len(parcelles) > 1,
        "tokens_non_reconnus": tokens_non_reconnus,
    }
