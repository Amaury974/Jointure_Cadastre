# -*- coding: utf-8 -*-
"""
Exécution de la jointure entre le tableau de données (normalisé) et la couche
de parcelles cadastrales, avec production d'une couche résultat et d'un rapport.
"""
from collections import defaultdict

from qgis.core import (
    QgsFeature,
    QgsVectorLayer,
    QgsField,
    QgsFields,
)
from qgis.PyQt.QtCore import QVariant

from .normalize import normaliser_parcelle


def executer_jointure(
    couche_table,
    colonne_table,
    couche_cadastre,
    champ_cadastre,
    options_normalisation,
    progress_callback=None,
):
    """
    Joint chaque ligne de `couche_table` à la géométrie correspondante dans
    `couche_cadastre`, en normalisant les numéros de parcelles des deux côtés.

    :return: (couche_resultat: QgsVectorLayer, rapport: dict)
    """
    # 1. Indexation de la couche cadastrale : numéro normalisé -> feature cadastre
    index_cadastre = defaultdict(list)
    total_cadastre = couche_cadastre.featureCount() or 1
    for i, feature_cadastre in enumerate(couche_cadastre.getFeatures()):
        valeur_brute = feature_cadastre[champ_cadastre]
        numero_normalise = normaliser_parcelle(valeur_brute, **options_normalisation)
        index_cadastre[numero_normalise].append(feature_cadastre)
        if progress_callback and i % 200 == 0:
            progress_callback(int(i * 50 / total_cadastre))  # 0-50% : indexation

    # 2. Préparation de la couche résultat : champs du tableau source + champs du cadastre
    champs_resultat = QgsFields()
    for champ in couche_table.fields():
        champs_resultat.append(champ)
    champs_resultat.append(QgsField("numero_parcelle_normalise", QVariant.String))
    champs_resultat.append(QgsField("statut_jointure", QVariant.String))

    couche_resultat = QgsVectorLayer(
        f"Polygon?crs={couche_cadastre.crs().authid()}",
        "resultat_jointure",
        "memory",
    )
    couche_resultat.dataProvider().addAttributes(champs_resultat)
    couche_resultat.updateFields()

    # 3. Parcours du tableau source, jointure ligne par ligne
    nb_trouves = 0
    nb_non_trouves = 0
    nb_doublons = 0
    non_trouves = []

    total_table = couche_table.featureCount() or 1
    nouvelles_features = []

    for i, feature_table in enumerate(couche_table.getFeatures()):
        valeur_brute = feature_table[colonne_table]
        numero_normalise = normaliser_parcelle(valeur_brute, **options_normalisation)

        correspondances = index_cadastre.get(numero_normalise, [])

        if not correspondances:
            nb_non_trouves += 1
            non_trouves.append(str(valeur_brute))
        else:
            if len(correspondances) > 1:
                nb_doublons += 1
            nb_trouves += 1

            for feature_cadastre in correspondances:
                nouvelle_feature = QgsFeature(champs_resultat)
                nouvelle_feature.setGeometry(feature_cadastre.geometry())

                for champ in couche_table.fields():
                    nouvelle_feature[champ.name()] = feature_table[champ.name()]
                nouvelle_feature["numero_parcelle_normalise"] = numero_normalise
                nouvelle_feature["statut_jointure"] = (
                    "doublon" if len(correspondances) > 1 else "ok"
                )
                nouvelles_features.append(nouvelle_feature)

        if progress_callback and i % 50 == 0:
            progress_callback(50 + int(i * 50 / total_table))  # 50-100% : jointure

    couche_resultat.dataProvider().addFeatures(nouvelles_features)
    couche_resultat.updateExtents()

    if progress_callback:
        progress_callback(100)

    rapport = {
        "nb_trouves": nb_trouves,
        "nb_non_trouves": nb_non_trouves,
        "nb_doublons": nb_doublons,
        "non_trouves": non_trouves,
    }
    return couche_resultat, rapport
