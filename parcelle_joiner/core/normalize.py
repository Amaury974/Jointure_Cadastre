# -*- coding: utf-8 -*-
"""
Normalisation / uniformisation des numéros de parcelles cadastrales.

Le format cadastral français "long" typique est :
    CCCCC PPP SS NNNN
    - CCCCC : code INSEE de la commune (5 chiffres)
    - PPP   : préfixe de section (3 chiffres, souvent "000")
    - SS    : lettre(s) de section (1 à 2 caractères)
    - NNNN  : numéro de parcelle (4 chiffres)

Ce module reste volontairement simple et isolé du reste du plugin :
il est testable indépendamment de QGIS (pas d'import qgis.core ici).
Adaptez les règles ci-dessous au format réel de vos données sources.
"""
import re

# Regex tolérante : capture commune, préfixe (optionnel), section (lettres), numéro
_PATTERN_PARCELLE = re.compile(
    r"^\s*(?P<commune>\d{1,5})?\s*[\.\-/ ]*"
    r"(?P<prefixe>\d{1,3})?\s*[\.\-/ ]*"
    r"(?P<section>[A-Za-z]{1,2})\s*[\.\-/ ]*"
    r"(?P<numero>\d{1,4})\s*$"
)


def normaliser_parcelle(
    valeur_brute,
    supprimer_separateurs=True,
    majuscules=True,
    padding=True,
    longueur_commune=5,
    longueur_prefixe=3,
    longueur_numero=4,
):
    """
    Normalise une chaîne représentant un numéro de parcelle.

    :param valeur_brute: la valeur telle que saisie dans le tableau source
    :param supprimer_separateurs: supprime espaces/tirets/points parasites avant analyse
    :param majuscules: force la section en majuscules
    :param padding: complète les zéros manquants sur commune/préfixe/numéro
    :return: chaîne normalisée, ou la valeur d'origine nettoyée si le format n'est pas reconnu
    """
    if valeur_brute is None:
        return ""

    valeur = str(valeur_brute).strip()
    if not valeur:
        return ""

    valeur_travail = valeur
    if supprimer_separateurs:
        # on garde temporairement un séparateur unique pour que la regex fonctionne
        valeur_travail = re.sub(r"[\s\-_/\.]+", " ", valeur_travail)

    match = _PATTERN_PARCELLE.match(valeur_travail)
    if not match:
        # Format non reconnu : on renvoie une version nettoyée (sans séparateurs), en majuscules
        valeur_secours = re.sub(r"[\s\-_/\.]+", "", valeur) if supprimer_separateurs else valeur
        return valeur_secours.upper() if majuscules else valeur_secours

    commune = match.group("commune") or ""
    prefixe = match.group("prefixe") or ""
    section = match.group("section") or ""
    numero = match.group("numero") or ""

    if majuscules:
        section = section.upper()

    if padding:
        commune = commune.zfill(longueur_commune) if commune else ""
        prefixe = prefixe.zfill(longueur_prefixe) if prefixe else "0" * longueur_prefixe
        numero = numero.zfill(longueur_numero) if numero else ""
        section = section.rjust(2, "0") if len(section) == 1 else section

    return f"{commune}{prefixe}{section}{numero}"
