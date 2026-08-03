# -*- coding: utf-8 -*-
"""
Lecture unifiée du tableau de données source, quel que soit son format :
CSV, XLSX (Excel) ou ODS (LibreOffice/OpenOffice Calc).

Choix technique : on s'appuie sur le driver OGR déjà fourni par QGIS/GDAL
plutôt que sur des bibliothèques Python tierces (pandas/openpyxl/odfpy).
Cela évite toute installation supplémentaire pour l'utilisateur : si QGIS
peut ouvrir un fichier Excel dans le panneau des couches, ce module peut le lire.

Pour les classeurs multi-feuilles (xlsx/ods), la liste des feuilles est
exposée via `lister_feuilles()` afin que l'interface puisse proposer un choix
à l'utilisateur ; par défaut la première feuille est utilisée.
"""
import os

from qgis.core import QgsVectorLayer, QgsProviderRegistry

EXTENSIONS_MULTI_FEUILLES = (".xlsx", ".xls", ".ods")


class TableSourceError(Exception):
    """Erreur levée lorsque le tableau de données source ne peut pas être chargé."""
    pass


def lister_feuilles(chemin):
    """
    Retourne la liste des noms de feuilles disponibles dans un classeur
    xlsx/ods. Retourne une liste vide si le fichier n'a qu'une seule table
    implicite (ex: CSV) ou si l'introspection échoue.
    """
    try:
        details = QgsProviderRegistry.instance().querySublayers(chemin)
        return [d.name() for d in details]
    except Exception:
        return []


def ouvrir_table_source(chemin, nom_feuille=None):
    """
    Ouvre le tableau de données source et retourne une QgsVectorLayer valide.

    :param chemin: chemin vers le fichier .csv, .xlsx, .xls ou .ods
    :param nom_feuille: nom de la feuille à utiliser pour les classeurs
        multi-feuilles (xlsx/ods). Si None, la première feuille est utilisée.
    :raises TableSourceError: si le fichier ne peut pas être ouvert
    """
    if not chemin or not os.path.exists(chemin):
        raise TableSourceError(f"Fichier introuvable : {chemin}")

    extension = os.path.splitext(chemin)[1].lower()

    if extension in EXTENSIONS_MULTI_FEUILLES:
        feuilles = lister_feuilles(chemin)
        if not feuilles:
            raise TableSourceError(
                f"Impossible de lister les feuilles du classeur : {chemin}\n"
                "Vérifiez que GDAL/OGR de QGIS est compilé avec le support "
                "XLSX/ODS (c'est le cas des installations QGIS standard)."
            )
        feuille = nom_feuille or feuilles[0]
        uri = f"{chemin}|layername={feuille}"
        couche = QgsVectorLayer(uri, "table_source", "ogr")
    else:
        couche = QgsVectorLayer(chemin, "table_source", "ogr")

    if not couche.isValid():
        raise TableSourceError(f"Le fichier n'a pas pu être chargé comme table : {chemin}")

    return couche


def extraire_echantillon(couche, colonne_liste=None, nb_lignes=25, max_lignes_scannees=2000):
    """
    Extrait un échantillon de valeurs par colonne, pour la détection
    automatique des rôles de colonnes (voir column_detector.py).

    Les lignes "fantômes" (quasi entièrement vides — moins de 2 champs
    renseignés) sont ignorées lors de l'échantillonnage. Ceci protège contre
    un artefact classique des fichiers Excel : une mise en forme (ex: format
    de date) appliquée à des centaines de lignes vides sous les données
    réelles, que le lecteur GDAL/OGR peut parfois restituer sous une forme
    trompeuse et fausser la détection automatique des colonnes.

    :param max_lignes_scannees: nombre maximal de lignes du fichier source
        parcourues pour constituer l'échantillon (au-delà de `nb_lignes`
        lignes utiles retenues), en cas de nombreuses lignes fantômes.
    :return: dict {nom_colonne: [valeurs...]}
    """
    noms_champs = colonne_liste or [f.name() for f in couche.fields()]
    echantillon = {nom: [] for nom in noms_champs}

    nb_retenues = 0
    for i, feature in enumerate(couche.getFeatures()):
        if i >= max_lignes_scannees or nb_retenues >= nb_lignes:
            break
        valeurs = {nom: feature[nom] for nom in noms_champs}
        nb_champs_non_vides = sum(1 for v in valeurs.values() if str(v).strip())
        if nb_champs_non_vides < 2:
            continue  # ligne probablement "fantôme" (mise en forme sans contenu réel)

        nb_retenues += 1
        for nom in noms_champs:
            echantillon[nom].append(valeurs[nom])

    return echantillon


def classifier_types_champs(couche):
    """
    Classe chaque champ de la couche en "texte" ou "autre", pour restreindre
    la détection automatique des colonnes (column_detector.py) aux seules
    colonnes de type texte : une colonne commune/section/numéro est toujours
    du texte, jamais une Date, une Heure ou un nombre à virgule (montants...).

    Ce filtrage protège structurellement contre les artefacts de mise en
    forme Excel évoqués dans extraire_echantillon() : même si une colonne de
    dates produit des valeurs fantômes ressemblant à des fragments de
    parcelle, son TYPE de champ reste Date/DateTime et elle est donc exclue
    d'office, quel que soit son contenu apparent.

    :return: dict {nom_champ: "texte" | "autre"}
    """
    from qgis.PyQt.QtCore import QVariant

    TYPES_TEXTE_AUTORISES = {QVariant.String, QVariant.Int, QVariant.LongLong}

    return {
        champ.name(): ("texte" if champ.type() in TYPES_TEXTE_AUTORISES else "autre")
        for champ in couche.fields()
    }
