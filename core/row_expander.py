# -*- coding: utf-8 -*-
"""
Étape de préparation des lignes du tableau source, avant jointure avec le
cadastre : identification de la commune, découpage des cellules contenant
plusieurs parcelles (avec duplication de ligne + avertissement), et
composition du code de parcelle normalisé.

Ne dépend que de commune_matcher / parcel_parser / normalize (pas de QGIS),
ce qui le rend testable indépendamment.
"""
import re

from .commune_matcher import identifier_commune
from .parcel_parser import decouper_parcelles, _PATTERN_SEPARATEURS
from .normalize import composer_code_parcelle
from .reunion_communes import construire_index_alias


def preparer_lignes_depuis_features(features_avec_attributs, config, options_normalisation):
    """
    :param features_avec_attributs: liste de dict représentant chaque ligne
        source (attribut -> valeur), déjà extraite de la couche/table (pour
        rester indépendant de QGIS dans ce module).
    :param config: dict décrivant le mode de saisie et les colonnes, voir
        column_detector.detecter_roles_colonnes() pour le format :
        {
            "mode": "colonnes_separees" | "section_numero_ensemble" | "tout_en_un",
            "colonne_commune": str,
            "colonne_parcelle_combinee": str | None,
            "colonne_section": str | None,
            "colonne_numero": str | None,
        }
    :param options_normalisation: dict passé à composer_code_parcelle
        (majuscules, padding, ...)

    :return: liste de dict, une entrée par PARCELLE (donc une ligne source
        avec 3 parcelles produit 3 entrées) :
        {
            "attributs_originaux": dict,
            "index_ligne_source": int,
            "commune_brute": str,
            "code_insee": str | None,
            "nom_commune": str | None,
            "section": str,
            "numero": str,
            "texte_parcelle_brut": str,   # valeur section+numéro telle que dans le tableau d'origine
            "code_parcelle_normalise": str,
            "nb_parcelles_ligne": int,
            "avertissements": [str, ...],
        }
    """
    mode = config["mode"]
    resultats = []

    for index_ligne, attributs in enumerate(features_avec_attributs):
        avertissements_ligne = []

        # --- 1. Identification de la commune ---
        if mode == "tout_en_un":
            texte_complet = str(attributs.get(config["colonne_commune"], ""))
            info_commune, texte_parcelles_restant = _extraire_commune_de_texte_complet(texte_complet)
        else:
            texte_commune_brut = attributs.get(config["colonne_commune"], "")
            info_commune = identifier_commune(texte_commune_brut)
            texte_parcelles_restant = None  # non utilisé hors mode "tout_en_un"

        if info_commune["code_insee"] is None:
            avertissements_ligne.append(
                f"Commune non reconnue ({info_commune['texte_normalise']!r}) — "
                "à corriger manuellement."
            )

        # --- 2. Découpage des parcelles (une ou plusieurs) ---
        if mode == "colonnes_separees":
            parcelles, fragments_bruts, avert_parcelles = _decouper_colonnes_separees(
                attributs.get(config["colonne_section"], ""),
                attributs.get(config["colonne_numero"], ""),
            )
        elif mode == "tout_en_un":
            resultat_decoupe = decouper_parcelles(texte_parcelles_restant or "")
            parcelles = resultat_decoupe["parcelles"]
            fragments_bruts = resultat_decoupe["fragments_bruts"]
            avert_parcelles = [
                f"Fragment de parcelle non reconnu : {t!r}"
                for t in resultat_decoupe["tokens_non_reconnus"]
            ]
        else:  # "section_numero_ensemble"
            valeur_brute = attributs.get(config["colonne_parcelle_combinee"], "")
            resultat_decoupe = decouper_parcelles(valeur_brute)
            parcelles = resultat_decoupe["parcelles"]
            fragments_bruts = resultat_decoupe["fragments_bruts"]
            avert_parcelles = [
                f"Fragment de parcelle non reconnu : {t!r}"
                for t in resultat_decoupe["tokens_non_reconnus"]
            ]

        avertissements_ligne.extend(avert_parcelles)

        if not parcelles:
            avertissements_ligne.append("Aucune parcelle exploitable trouvée sur cette ligne.")
            parcelles = [("", "")]  # on produit quand même une ligne (vide) pour ne rien perdre
            fragments_bruts = [""]

        nb_parcelles = len(parcelles)
        if nb_parcelles > 1:
            avertissement_multiple = (
                f"{nb_parcelles} parcelles détectées sur cette ligne — ligne dupliquée."
            )
        else:
            avertissement_multiple = None

        for j, (section, numero) in enumerate(parcelles):
            avertissements = list(avertissements_ligne)
            if avertissement_multiple:
                avertissements.append(avertissement_multiple)

            code_parcelle = ""
            if info_commune["code_insee"] and (section or numero):
                code_parcelle = composer_code_parcelle(
                    info_commune["code_insee"], section, numero, **options_normalisation
                )

            texte_parcelle_brut = fragments_bruts[j] if j < len(fragments_bruts) else f"{section}{numero}"

            resultats.append({
                "attributs_originaux": attributs,
                "index_ligne_source": index_ligne,
                "commune_brute": attributs.get(config["colonne_commune"], ""),
                "code_insee": info_commune["code_insee"],
                "nom_commune": info_commune["nom_officiel"],
                "section": section,
                "numero": numero,
                "texte_parcelle_brut": texte_parcelle_brut,
                "code_parcelle_normalise": code_parcelle,
                "nb_parcelles_ligne": nb_parcelles,
                "avertissements": avertissements,
            })

    return resultats


def _decouper_colonnes_separees(valeur_section, valeur_numero):
    """
    Cas "colonnes séparées" : section et numéro sont chacun dans leur propre
    colonne. On gère quand même le cas de plusieurs valeurs dans une même
    cellule (ex: section="AB, CD" / numero="12, 34"), en les découpant avec
    les mêmes séparateurs que decouper_parcelles, puis en les appariant par position.

    :return: (parcelles, fragments_bruts, avertissements) — `fragments_bruts`
        est aligné 1-pour-1 avec `parcelles` et représente la concaténation
        "section numéro" telle que saisie à l'origine (avant mise en
        majuscules), pour affichage dans l'aperçu.
    """
    sections_brutes = [s.strip() for s in _PATTERN_SEPARATEURS.split(str(valeur_section)) if s.strip()]
    numeros_brutes = [n.strip() for n in _PATTERN_SEPARATEURS.split(str(valeur_numero)) if n.strip()]
    sections = [s.upper() for s in sections_brutes]
    numeros = numeros_brutes

    avertissements = []

    if not sections and not numeros:
        return [], [], avertissements

    if len(sections) <= 1 and len(numeros) <= 1:
        section = sections[0] if sections else ""
        numero = numeros[0] if numeros else ""
        section_brute = sections_brutes[0] if sections_brutes else ""
        numero_brut = numeros_brutes[0] if numeros_brutes else ""
        texte_brut = f"{section_brute} {numero_brut}".strip()
        return [(section, numero)], [texte_brut], avertissements

    if len(sections) != len(numeros):
        avertissements.append(
            "Nombre de sections et de numéros différent sur cette ligne : "
            "appariement par position, à vérifier."
        )

    if sections:
        parcelles = list(zip(sections, numeros))
        fragments_bruts = [f"{s} {n}".strip() for s, n in zip(sections_brutes, numeros_brutes)]
    else:
        parcelles = [("", n) for n in numeros]
        fragments_bruts = list(numeros_brutes)

    return parcelles, fragments_bruts, avertissements


def _extraire_commune_de_texte_complet(texte_complet):
    """
    Cas "tout en un" (commune + section + numéro dans la même chaîne) :
    recherche du plus long alias de commune reconnu comme sous-chaîne du
    texte, puis renvoie (info_commune, reste_du_texte_pour_la_parcelle).

    Approche best-effort : sans exemple réel de ce format, cette fonction
    privilégie la robustesse (ne jamais planter) plutôt que l'exactitude
    parfaite. Vérifiez le résultat via l'aperçu avant de lancer un traitement complet.
    """
    from .commune_matcher import normaliser_nom_commune

    texte_normalise = normaliser_nom_commune(texte_complet)
    index_alias = construire_index_alias()

    meilleur_alias = None
    for alias_normalise in index_alias:
        if alias_normalise and alias_normalise in texte_normalise:
            if meilleur_alias is None or len(alias_normalise) > len(meilleur_alias):
                meilleur_alias = alias_normalise

    if meilleur_alias is None:
        info_commune = identifier_commune(texte_complet)  # tentera une correspondance approchée
        return info_commune, texte_complet

    code_insee, nom_officiel = index_alias[meilleur_alias]
    info_commune = {
        "code_insee": code_insee, "nom_officiel": nom_officiel,
        "methode": "sous-chaine", "texte_normalise": meilleur_alias,
    }

    # Retire la sous-chaîne correspondante (au mieux) pour isoler le reste
    # (numéro de commune éventuel + section + numéro de parcelle)
    reste = re.sub(re.escape(meilleur_alias), " ", texte_normalise, flags=re.IGNORECASE)
    # Le reste peut contenir le code commune en chiffres (à ignorer) : on ne garde
    # que le dernier groupe alphanumérique ressemblant à une parcelle.
    reste = re.sub(r"^\d+\s*", "", reste.strip())
    return info_commune, reste
