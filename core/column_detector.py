# -*- coding: utf-8 -*-
"""
Détection automatique du rôle de chaque colonne du tableau source, pour
pré-remplir l'interface (l'utilisateur garde toujours la main pour corriger).

Trois configurations possibles, conformément aux besoins exprimés :
    - "colonnes_separees"        : commune / section / numéro sont dans 3 colonnes distinctes
    - "section_numero_ensemble"  : commune dans une colonne, "section+numéro" combinés dans une autre
    - "tout_en_un"               : commune + section + numéro combinés dans une seule et même colonne

Détection MIXTE, combinant deux signaux :
    1. Le NOM des colonnes (en-têtes) : un signal fort et indépendant du
       contenu — une colonne intitulée "N° de parcelle(s)" ou "Commune" est
       un indice quasi certain, alors qu'une colonne "Date du paiement" ou
       "Montant" doit être exclue d'office, quel que soit son contenu. C'est
       le signal prioritaire.
    2. Le CONTENU de la colonne (comme avant : correspondance avec le
       référentiel des communes / le parseur de parcelles) : utilisé en
       complément pour les rôles que les en-têtes n'ont pas permis de
       résoudre (en-têtes non explicites, absentes, ou ambiguës).

Cette approche mixte protège notamment contre un phénomène observé en
pratique : une colonne de dates peut, selon la façon dont GDAL/OGR restitue
les valeurs d'un fichier Excel (représentation textuelle d'une date avec
séparateurs "/", ou artefacts sur des cellules vides mises en forme),
ressembler fortuitement à des fragments de numéro de parcelle et obtenir un
meilleur score de contenu que la véritable colonne de parcelles. Le nom de
la colonne ("Date du paiement") suffit à écarter ce cas, indépendamment de
ce que le contenu donne à voir.
"""
import re
import unicodedata

from .commune_matcher import identifier_commune
from .parcel_parser import decouper_parcelles

_SEUIL_DETECTION = 0.6  # fraction de valeurs de l'échantillon qui doivent matcher (voie "contenu")

_PATTERN_SECTION_SEULE = re.compile(r"^[A-Za-z]{1,2}$")
_PATTERN_NUMERO_SEUL = re.compile(r"^\d+$")

# Mots-clés recherchés dans les noms de colonnes (comparaison insensible aux
# accents/casse, sur une simple inclusion de sous-chaîne).
_MOTS_CLE_COMMUNE = ("commune",)
_MOTS_CLE_PARCELLE = ("parcelle",)
_MOTS_CLE_SECTION = ("section",)
_MOTS_CLE_NUMERO = ("numero", "n°", "no parcelle", "num parcelle")
# Colonnes à exclure d'office de la détection, quel que soit leur contenu :
# dates, montants, et autres colonnes typiques d'un tableau de subventions
# qui n'ont rien à voir avec une commune ou une parcelle.
_MOTS_CLE_EXCLUSION = (
    "date", "montant", "prix", "cout", "coût", "subvention", "paiement",
    "surface", "superficie", "observation", "commentaire", "remarque",
)


def _normaliser_entete(nom_colonne):
    """Sans accents, en minuscules, espaces multiples réduits — pour comparaison par mots-clés."""
    texte = unicodedata.normalize("NFKD", str(nom_colonne))
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    texte = re.sub(r"\s+", " ", texte.strip().lower())
    return texte


def _entete_contient(nom_colonne, mots_cle):
    entete = _normaliser_entete(nom_colonne)
    return any(mot in entete for mot in mots_cle)


def _detecter_par_entete(noms_colonnes):
    """
    Analyse uniquement les noms de colonnes (aucun contenu), et retourne un
    dict décrivant les rôles identifiés avec certitude par mots-clés, ainsi
    que l'ensemble des colonnes à exclure de toute détection par contenu.
    """
    colonnes_exclues = {c for c in noms_colonnes if _entete_contient(c, _MOTS_CLE_EXCLUSION)}
    candidates = [c for c in noms_colonnes if c not in colonnes_exclues]

    return {
        "colonne_commune": next((c for c in candidates if _entete_contient(c, _MOTS_CLE_COMMUNE)), None),
        "colonne_parcelle_combinee": next((c for c in candidates if _entete_contient(c, _MOTS_CLE_PARCELLE)), None),
        "colonne_section": next((c for c in candidates if _entete_contient(c, _MOTS_CLE_SECTION)), None),
        "colonne_numero": next((c for c in candidates if _entete_contient(c, _MOTS_CLE_NUMERO)), None),
        "colonnes_exclues": colonnes_exclues,
    }


def _valeurs_non_vides(valeurs):
    return [str(v).strip() for v in valeurs if str(v).strip()]


def _scorer_colonnes(echantillon):
    """Calcule, pour chaque colonne, la fraction de valeurs correspondant à chaque rôle possible."""
    scores = {}
    for colonne, valeurs in echantillon.items():
        non_vides = _valeurs_non_vides(valeurs)
        if not non_vides:
            continue
        n = len(non_vides)

        n_commune = sum(1 for v in non_vides if identifier_commune(v)["code_insee"] is not None)
        n_parcelle = sum(
            1 for v in non_vides
            if decouper_parcelles(v)["parcelles"] and not decouper_parcelles(v)["tokens_non_reconnus"]
        )
        n_section_seule = sum(1 for v in non_vides if _PATTERN_SECTION_SEULE.match(v))
        n_numero_seul = sum(1 for v in non_vides if _PATTERN_NUMERO_SEUL.match(v))

        scores[colonne] = {
            "frac_commune": n_commune / n,
            "frac_parcelle": n_parcelle / n,
            "frac_section_seule": n_section_seule / n,
            "frac_numero_seul": n_numero_seul / n,
        }
    return scores


def _meilleure_colonne(scores, cle_score, exclure=()):
    candidats = {c: s for c, s in scores.items() if c not in exclure}
    if not candidats:
        return None
    meilleure = max(candidats, key=lambda c: candidats[c][cle_score])
    if candidats[meilleure][cle_score] < _SEUIL_DETECTION:
        return None
    return meilleure


def detecter_roles_colonnes(echantillon, types_colonnes=None):
    """
    :param echantillon: dict {nom_colonne: [valeurs échantillonnées]}
    :param types_colonnes: dict optionnel {nom_colonne: "texte"|"autre"} — voir
        table_reader.classifier_types_champs(). Quand fourni, seules les
        colonnes de type "texte" sont candidates pour un rôle commune/section/
        numéro lors de la détection par CONTENU (les indices tirés du NOM des
        colonnes, eux, s'appliquent indépendamment du type). Si omis, aucun
        filtrage par type n'est appliqué (utile pour les tests unitaires purs
        Python).
    :return: dict {
        "mode": "colonnes_separees" | "section_numero_ensemble" | "tout_en_un",
        "colonne_commune": str|None,
        "colonne_parcelle_combinee": str|None,
        "colonne_section": str|None,
        "colonne_numero": str|None,
    }
    """
    noms_colonnes = list(echantillon.keys())
    indices_entete = _detecter_par_entete(noms_colonnes)
    colonnes_exclues = indices_entete["colonnes_exclues"]

    # L'échantillon utilisé pour le scoring par CONTENU exclut les colonnes
    # écartées par leur nom (dates, montants...) et, si fourni, celles dont
    # le type de champ n'est pas textuel.
    echantillon_filtre = {
        colonne: valeurs for colonne, valeurs in echantillon.items()
        if colonne not in colonnes_exclues
        and (not types_colonnes or types_colonnes.get(colonne, "texte") == "texte")
    }
    scores = _scorer_colonnes(echantillon_filtre)

    colonne_commune = indices_entete["colonne_commune"] or _meilleure_colonne(scores, "frac_commune")
    colonne_section = indices_entete["colonne_section"] or _meilleure_colonne(
        scores, "frac_section_seule", exclure={colonne_commune}
    )
    colonne_numero = indices_entete["colonne_numero"] or _meilleure_colonne(
        scores, "frac_numero_seul", exclure={colonne_commune, colonne_section}
    )

    resultat = {
        "mode": None,
        "colonne_commune": colonne_commune,
        "colonne_parcelle_combinee": None,
        "colonne_section": None,
        "colonne_numero": None,
    }

    if colonne_section and colonne_numero and colonne_section != colonne_numero:
        resultat["mode"] = "colonnes_separees"
        resultat["colonne_section"] = colonne_section
        resultat["colonne_numero"] = colonne_numero
        return resultat

    colonne_parcelle = indices_entete["colonne_parcelle_combinee"] or _meilleure_colonne(
        scores, "frac_parcelle", exclure={colonne_commune}
    )

    if colonne_commune and colonne_parcelle:
        resultat["mode"] = "section_numero_ensemble"
        resultat["colonne_parcelle_combinee"] = colonne_parcelle
        return resultat

    if colonne_commune is None and colonne_parcelle:
        # Une seule colonne semble tout contenir (commune + section + numéro)
        resultat["mode"] = "tout_en_un"
        resultat["colonne_parcelle_combinee"] = colonne_parcelle
        resultat["colonne_commune"] = colonne_parcelle
        return resultat

    # Rien de concluant : on laisse l'utilisateur tout configurer manuellement
    resultat["mode"] = "section_numero_ensemble"
    return resultat
