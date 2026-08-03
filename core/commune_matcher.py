# -*- coding: utf-8 -*-
"""
Reconnaissance du nom de commune à partir d'un texte brut, avec plusieurs
formats d'entrée possibles :
    - "97480 - Saint-Joseph"   (code postal + nom, séparés par un tiret)
    - "SAINT BENOIT"           (nom seul, sans accents, sans tiret)
    - "97411"                  (code INSEE seul, sans nom accolé — voir plus bas)

Stratégie :
    1. Si le texte contient un préfixe "code postal - ...", on ne garde que
       la partie textuelle (le code postal n'est pas fiable pour retrouver
       le code INSEE : plusieurs communes réunionnaises ont plusieurs codes
       postaux, et certains codes postaux coïncident même avec le code INSEE
       d'une AUTRE commune — ex: 97412 est à la fois un code postal de
       Bras-Panon et le code INSEE de Saint-Joseph). On matche donc toujours
       sur le NOM dans ce cas, jamais sur le nombre.
    2. Normalisation : suppression des accents, mise en majuscules,
       remplacement des apostrophes/tirets par des espaces, espaces multiples
       réduits.
    3. Recherche exacte dans l'index d'alias (reunion_communes.py).
    4. Si la valeur brute est un code INSEE valide à 5 chiffres SEUL (sans
       nom accolé — donc non capté par l'étape 1), reconnaissance directe par
       code INSEE. N'est tenté qu'en repli, après l'échec de la recherche par
       nom, pour ne jamais court-circuiter un nom explicitement fourni.
    5. À défaut, recherche approchée (difflib) pour absorber les fautes de
       frappe légères ; en dessous d'un seuil de similarité, on renvoie
       "non reconnu" pour laisser l'utilisateur corriger manuellement.
"""
import difflib
import re
import unicodedata

from .reunion_communes import construire_index_alias, construire_index_codes_insee

_PATTERN_CODE_POSTAL_PREFIXE = re.compile(r"^\s*\d{5}\s*[-–—]\s*(?P<nom>.+?)\s*$")
_PATTERN_CODE_INSEE_SEUL = re.compile(r"^\d{5}$")

_SEUIL_SIMILARITE = 0.82

_INDEX_ALIAS = None  # construit paresseusement (lazy) au premier appel
_INDEX_CODES_INSEE = None


def _get_index_alias():
    global _INDEX_ALIAS
    if _INDEX_ALIAS is None:
        _INDEX_ALIAS = construire_index_alias()
    return _INDEX_ALIAS


def _get_index_codes_insee():
    global _INDEX_CODES_INSEE
    if _INDEX_CODES_INSEE is None:
        _INDEX_CODES_INSEE = construire_index_codes_insee()
    return _INDEX_CODES_INSEE


def _extraire_code_insee_brut(valeur):
    """
    Convertit une valeur brute (str, int ou float — un tableur peut stocker
    un code commune comme nombre) en chaîne de 5 chiffres si la forme s'y
    prête, sinon None. Gère notamment le cas d'un export Excel d'une colonne
    numérique restituant "97411.0" plutôt que "97411".
    """
    if valeur is None or isinstance(valeur, bool):
        return None

    if isinstance(valeur, int):
        texte = str(valeur)
    elif isinstance(valeur, float):
        if not valeur.is_integer():
            return None
        texte = str(int(valeur))
    else:
        texte = str(valeur).strip()
        if re.match(r"^\d+\.0+$", texte):
            texte = texte.split(".")[0]

    return texte if _PATTERN_CODE_INSEE_SEUL.match(texte) else None


def normaliser_nom_commune(texte):
    """
    Normalise un nom de commune pour comparaison :
    majuscules, sans accents, apostrophes/tirets -> espace, espaces réduits.
    """
    if texte is None:
        return ""
    texte = str(texte).strip()

    # Retire un éventuel préfixe "code postal - "
    match = _PATTERN_CODE_POSTAL_PREFIXE.match(texte)
    if match:
        texte = match.group("nom")

    # Suppression des accents
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))

    texte = texte.upper()
    texte = re.sub(r"[\'\-_]", " ", texte)
    texte = re.sub(r"\s+", " ", texte).strip()
    return texte


def identifier_commune(texte_brut):
    """
    Tente d'identifier la commune réunionnaise correspondant à `texte_brut`.

    :return: dict avec :
        - "code_insee" : code à 5 chiffres, ou None si non reconnu
        - "nom_officiel" : nom officiel de la commune, ou None
        - "methode" : "exact", "code_insee", "approché" ou "non_reconnu"
        - "texte_normalise" : la version normalisée utilisée pour la recherche
    """
    texte_normalise = normaliser_nom_commune(texte_brut)
    index = _get_index_alias()

    if not texte_normalise:
        return {
            "code_insee": None, "nom_officiel": None,
            "methode": "non_reconnu", "texte_normalise": texte_normalise,
        }

    # 1. Recherche exacte par nom
    if texte_normalise in index:
        code_insee, nom_officiel = index[texte_normalise]
        return {
            "code_insee": code_insee, "nom_officiel": nom_officiel,
            "methode": "exact", "texte_normalise": texte_normalise,
        }

    # 2. Reconnaissance directe par code INSEE (valeur brute = code seul,
    #    ex: "97411", sans nom accolé — sinon l'étape 1 aurait déjà résolu
    #    via le préfixe "code postal - nom" le cas échéant)
    code_brut = _extraire_code_insee_brut(texte_brut)
    if code_brut:
        nom_officiel = _get_index_codes_insee().get(code_brut)
        if nom_officiel:
            return {
                "code_insee": code_brut, "nom_officiel": nom_officiel,
                "methode": "code_insee", "texte_normalise": texte_normalise,
            }

    # 3. Recherche approchée (fautes de frappe, variantes non prévues)
    candidats = difflib.get_close_matches(
        texte_normalise, index.keys(), n=1, cutoff=_SEUIL_SIMILARITE
    )
    if candidats:
        code_insee, nom_officiel = index[candidats[0]]
        return {
            "code_insee": code_insee, "nom_officiel": nom_officiel,
            "methode": "approché", "texte_normalise": texte_normalise,
        }

    # 4. Non reconnu : à corriger manuellement par l'utilisateur
    return {
        "code_insee": None, "nom_officiel": None,
        "methode": "non_reconnu", "texte_normalise": texte_normalise,
    }
