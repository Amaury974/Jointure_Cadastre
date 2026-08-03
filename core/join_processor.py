# -*- coding: utf-8 -*-
"""
Exécution de la jointure entre le tableau de données (préparé/normalisé) et
la couche de parcelles cadastrales, avec production d'une couche résultat et
d'un rapport détaillé.

Ce module fait le pont entre row_expander.py (logique métier pure Python) et
QGIS (lecture de la couche cadastrale, construction de la couche résultat).

Le traitement est volontairement scindé en deux étapes distinctes :
    1. preparer_lignes_table()  : identifie les communes / découpe les
       parcelles à partir du tableau source SEUL (aucune dépendance au
       cadastre). Ceci permet de connaître à l'avance l'ensemble des communes
       réellement nécessaires, et donc de ne récupérer QUE ces communes-là
       si l'on utilise la récupération automatique via data.gouv.fr
       (voir cadastre_source.py) plutôt qu'une couche de référence complète.
    2. joindre_avec_cadastre()  : effectue la jointure proprement dite une
       fois la couche cadastrale (quelle qu'en soit la source) disponible.
"""
from collections import defaultdict

from qgis.core import QgsFeature, QgsVectorLayer, QgsField, QgsFields
from qgis.PyQt.QtCore import QVariant

from .row_expander import preparer_lignes_depuis_features


def preparer_lignes_table(couche_table, config_colonnes, options_normalisation):
    """
    Extrait et prépare les lignes du tableau source (identification commune,
    découpage des parcelles multiples), sans toucher au cadastre.

    :return: liste de lignes préparées (voir row_expander.preparer_lignes_depuis_features)
    """
    noms_champs = [f.name() for f in couche_table.fields()]
    features_avec_attributs = []
    for feature in couche_table.getFeatures():
        features_avec_attributs.append({nom: feature[nom] for nom in noms_champs})

    return preparer_lignes_depuis_features(
        features_avec_attributs, config_colonnes, options_normalisation
    )


def codes_insee_necessaires(lignes_preparees):
    """Retourne l'ensemble des codes INSEE distincts (non None) présents dans les lignes préparées."""
    return {l["code_insee"] for l in lignes_preparees if l["code_insee"]}


def joindre_avec_cadastre(
    lignes_preparees,
    champs_table,
    couche_cadastre,
    champ_cadastre,
    options_normalisation,
    progress_callback=None,
):
    """
    :param lignes_preparees: sortie de preparer_lignes_table()
    :param champs_table: QgsFields du tableau source (pour conserver les types
        d'origine dans la couche résultat plutôt que tout convertir en texte)
    :param couche_cadastre: QgsVectorLayer des parcelles cadastrales
    :param champ_cadastre: nom du champ contenant le numéro de parcelle complet
        dans la couche cadastrale (ex: "id" pour les données Etalab, ou le
        champ équivalent d'une couche FTP/locale)
    :param options_normalisation: dict transmis à normaliser_parcelle pour
        la normalisation du champ cadastral (mêmes options que côté source)
    :param progress_callback: fonction optionnelle appelée avec un pourcentage (0-100)

    :return: (couche_resultat: QgsVectorLayer polygone, couche_non_reconnues:
        QgsVectorLayer sans géométrie (table), rapport: dict). Les parcelles
        pour lesquelles aucune correspondance cadastrale n'a été trouvée
        (commune non reconnue ou numéro absent du cadastre) sont placées
        dans `couche_non_reconnues` (une table, sans géométrie) plutôt que
        mêlées à la couche polygone — plus simple à repérer/corriger/exporter.
    """
    from .normalize import normaliser_parcelle

    # 1. Indexation de la couche cadastrale : numéro complet -> feature(s) cadastre
    index_cadastre = defaultdict(list)
    total_cadastre = couche_cadastre.featureCount() or 1
    for i, feature_cadastre in enumerate(couche_cadastre.getFeatures()):
        valeur_brute = feature_cadastre[champ_cadastre]
        cle = normaliser_parcelle(valeur_brute, **options_normalisation)
        index_cadastre[cle].append(feature_cadastre)
        if progress_callback and i % 200 == 0:
            progress_callback(int(i * 40 / total_cadastre))  # 0-40% : indexation cadastre

    if progress_callback:
        progress_callback(50)

    # 2. Préparation des champs communs aux deux couches de sortie
    champs_resultat = QgsFields()
    for champ in champs_table:
        champs_resultat.append(champ)
    champs_resultat.append(QgsField("commune_detectee", QVariant.String))
    champs_resultat.append(QgsField("code_insee_commune", QVariant.String))
    champs_resultat.append(QgsField("section", QVariant.String))
    champs_resultat.append(QgsField("numero_parcelle", QVariant.String))
    champs_resultat.append(QgsField("numero_parcelle_normalise", QVariant.String))
    champs_resultat.append(QgsField("statut_jointure", QVariant.String))
    champs_resultat.append(QgsField("avertissements", QVariant.String))

    couche_resultat = QgsVectorLayer(
        f"Polygon?crs={couche_cadastre.crs().authid()}",
        "resultat_jointure",
        "memory",
    )
    couche_resultat.dataProvider().addAttributes(champs_resultat)
    couche_resultat.updateFields()

    # Table sans géométrie pour les parcelles non reconnues (commune non
    # identifiée ou numéro introuvable dans le cadastre) — même structure de
    # champs que la couche polygone, pour rester facile à croiser/exporter.
    couche_non_reconnues = QgsVectorLayer("None", "parcelles_non_reconnues", "memory")
    couche_non_reconnues.dataProvider().addAttributes(champs_resultat)
    couche_non_reconnues.updateFields()

    # 3. Jointure ligne préparée <-> cadastre + répartition dans les 2 couches
    nb_trouves = 0
    nb_non_trouves = 0
    nb_doublons_cadastre = 0
    nb_lignes_dupliquees = 0
    nb_commune_non_reconnue = 0
    non_trouves = []

    total = len(lignes_preparees) or 1
    features_resultat = []
    features_non_reconnues = []

    for i, ligne in enumerate(lignes_preparees):
        code = ligne["code_parcelle_normalise"]
        correspondances = index_cadastre.get(code, []) if code else []

        if ligne["nb_parcelles_ligne"] > 1:
            nb_lignes_dupliquees += 1
        if ligne["code_insee"] is None:
            nb_commune_non_reconnue += 1

        if not correspondances:
            nb_non_trouves += 1
            non_trouves.append(code or ligne["commune_brute"])
            statut = "commune_non_reconnue" if ligne["code_insee"] is None else "non_trouve"
            features_non_reconnues.append(
                _construire_feature(champs_resultat, None, ligne, statut)
            )
        else:
            if len(correspondances) > 1:
                nb_doublons_cadastre += 1
            nb_trouves += 1
            statut = "doublon_cadastre" if len(correspondances) > 1 else "ok"
            for feature_cadastre in correspondances:
                features_resultat.append(
                    _construire_feature(champs_resultat, feature_cadastre, ligne, statut)
                )

        if progress_callback and i % 50 == 0:
            progress_callback(50 + int(i * 50 / total))

    couche_resultat.dataProvider().addFeatures(features_resultat)
    couche_resultat.updateExtents()
    couche_non_reconnues.dataProvider().addFeatures(features_non_reconnues)

    if progress_callback:
        progress_callback(100)

    rapport = {
        "nb_lignes_source": len({l["index_ligne_source"] for l in lignes_preparees}),
        "nb_parcelles_total": len(lignes_preparees),
        "nb_lignes_dupliquees": nb_lignes_dupliquees,
        "nb_trouves": nb_trouves,
        "nb_non_trouves": nb_non_trouves,
        "nb_doublons_cadastre": nb_doublons_cadastre,
        "nb_commune_non_reconnue": nb_commune_non_reconnue,
        "non_trouves": non_trouves,
    }
    return couche_resultat, couche_non_reconnues, rapport


def _construire_feature(champs_resultat, feature_cadastre, ligne, statut):
    nouvelle_feature = QgsFeature(champs_resultat)
    if feature_cadastre is not None:
        nouvelle_feature.setGeometry(feature_cadastre.geometry())

    for nom, valeur in ligne["attributs_originaux"].items():
        nouvelle_feature[nom] = valeur

    nouvelle_feature["commune_detectee"] = ligne["nom_commune"] or ""
    nouvelle_feature["code_insee_commune"] = ligne["code_insee"] or ""
    nouvelle_feature["section"] = ligne["section"]
    nouvelle_feature["numero_parcelle"] = ligne["numero"]
    nouvelle_feature["numero_parcelle_normalise"] = ligne["code_parcelle_normalise"]
    nouvelle_feature["statut_jointure"] = statut
    nouvelle_feature["avertissements"] = " | ".join(ligne["avertissements"])
    return nouvelle_feature
