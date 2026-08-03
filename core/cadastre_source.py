# -*- coding: utf-8 -*-
"""
Récupération automatique des parcelles cadastrales via le service ouvert
"Cadastre Etalab" (cadastre.data.gouv.fr, DINUM) — gratuit, sans clé d'API,
mis à jour plusieurs fois par an à partir du PCI Vecteur de la DGFiP.

Documentation : https://cadastre.data.gouv.fr/datasets/cadastre-etalab

Chaque commune est disponible en téléchargement direct au format GeoJSON
compressé, à l'URL :
    https://cadastre.data.gouv.fr/data/etalab-cadastre/{millesime}/geojson/communes/{dept}/{code_insee}/cadastre-{code_insee}-parcelles.json.gz

où {millesime} peut être "latest" pour toujours obtenir la version la plus
récente, {dept} est le code département (3 chiffres pour les DROM : 971-976),
et {code_insee} le code INSEE complet de la commune (5 caractères).

Intérêt par rapport à un téléchargement départemental complet : comme ce
plugin identifie déjà la commune de chaque ligne du tableau source (voir
commune_matcher.py), on ne télécharge QUE les communes effectivement
présentes dans les données à joindre — beaucoup plus rapide qu'un
téléchargement de couche de référence complète.

Le champ "id" du GeoJSON Etalab contient déjà le numéro de parcelle complet
(commune + préfixe + section + numéro), ce qui en fait directement la clé de
jointure à utiliser (voir champ_cadastre="id" côté dialog/join_processor).
"""
import gzip
import os
import tempfile
import time

BASE_URL = "https://cadastre.data.gouv.fr/data/etalab-cadastre/latest/geojson/communes"

CACHE_DIR = os.path.join(tempfile.gettempdir(), "parcelle_joiner_cache", "cadastre_etalab")
CACHE_MAX_AGE_SECONDES = 30 * 24 * 3600  # un nouveau millésime paraît tous les 2-3 mois


class CadastreSourceError(Exception):
    """Erreur levée quand une commune ne peut pas être récupérée depuis data.gouv.fr."""
    pass


def departement_depuis_insee(code_insee):
    """
    Déduit le code département (pour l'URL de téléchargement) à partir d'un
    code INSEE de commune. DROM (La Réunion, Guadeloupe, etc.) : 3 chiffres.
    Corse : déjà au format "2A"/"2B" dans le code INSEE lui-même.
    """
    if code_insee[:2] in ("97", "98"):
        return code_insee[:3]
    return code_insee[:2]


def url_commune(code_insee, source="parcelles"):
    dept = departement_depuis_insee(code_insee)
    return f"{BASE_URL}/{dept}/{code_insee}/cadastre-{code_insee}-{source}.json.gz"


def _cache_valide(chemin_local):
    if not os.path.exists(chemin_local):
        return False
    age = time.time() - os.path.getmtime(chemin_local)
    return age < CACHE_MAX_AGE_SECONDES


def telecharger_commune(code_insee, source="parcelles", forcer=False):
    """
    Télécharge (si besoin, sinon utilise le cache local) le GeoJSON des
    parcelles d'une commune et le décompresse.

    :return: chemin vers le fichier .geojson local (décompressé)
    :raises CadastreSourceError: en cas d'échec réseau ou de commune introuvable
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    chemin_local = os.path.join(CACHE_DIR, f"{code_insee}-{source}.geojson")

    if not forcer and _cache_valide(chemin_local):
        return chemin_local

    url = url_commune(code_insee, source)

    from qgis.core import QgsBlockingNetworkRequest
    from qgis.PyQt.QtNetwork import QNetworkRequest
    from qgis.PyQt.QtCore import QUrl

    requete = QgsBlockingNetworkRequest()
    resultat = requete.get(QNetworkRequest(QUrl(url)))

    if resultat != QgsBlockingNetworkRequest.NoError:
        raise CadastreSourceError(
            f"Impossible de télécharger la commune {code_insee} ({url}) : "
            f"{requete.errorMessage()}"
        )

    reponse = requete.reply()
    contenu_compresse = bytes(reponse.content())

    try:
        contenu_json = gzip.decompress(contenu_compresse)
    except OSError as e:
        raise CadastreSourceError(
            f"Réponse invalide pour la commune {code_insee} (pas un GeoJSON compressé "
            f"valide — la commune existe-t-elle bien dans le PCI Vecteur ?) : {e}"
        ) from e

    chemin_temp = chemin_local + ".tmp"
    with open(chemin_temp, "wb") as f:
        f.write(contenu_json)
    os.replace(chemin_temp, chemin_local)

    return chemin_local


def charger_couche_cadastre_communes(codes_insee, progress_callback=None, forcer=False):
    """
    Télécharge (avec cache) et fusionne en une seule QgsVectorLayer mémoire
    les parcelles des communes demandées.

    :param codes_insee: itérable de codes INSEE (str) à récupérer
    :param progress_callback: fonction optionnelle appelée avec un pourcentage (0-100)
    :param forcer: si True, ignore le cache local et retélécharge tout

    :return: (couche_resultat: QgsVectorLayer, communes_en_echec: dict{code_insee: message})
    """
    codes_uniques = sorted({c for c in codes_insee if c})
    if not codes_uniques:
        raise CadastreSourceError("Aucun code INSEE valide à récupérer.")

    from qgis.core import QgsVectorLayer

    couche_resultat = None
    communes_en_echec = {}
    total = len(codes_uniques)

    for i, code_insee in enumerate(codes_uniques):
        try:
            chemin_local = telecharger_commune(code_insee, forcer=forcer)
            couche_commune = QgsVectorLayer(chemin_local, f"cadastre_{code_insee}", "ogr")
            if not couche_commune.isValid():
                raise CadastreSourceError(f"GeoJSON invalide pour la commune {code_insee}.")

            if couche_resultat is None:
                couche_resultat = QgsVectorLayer(
                    f"Polygon?crs={couche_commune.crs().authid()}",
                    "cadastre_communes_selectionnees",
                    "memory",
                )
                couche_resultat.dataProvider().addAttributes(couche_commune.fields())
                couche_resultat.updateFields()

            _copier_features(couche_commune, couche_resultat)

        except CadastreSourceError as e:
            communes_en_echec[code_insee] = str(e)

        if progress_callback:
            progress_callback(int((i + 1) * 100 / total))

    if couche_resultat is None:
        raise CadastreSourceError(
            "Aucune commune n'a pu être récupérée : " + "; ".join(communes_en_echec.values())
        )

    couche_resultat.updateExtents()
    return couche_resultat, communes_en_echec


def _copier_features(couche_source, couche_cible):
    """Copie les features de couche_source dans couche_cible (même structure de champs)."""
    from qgis.core import QgsFeature

    noms_champs_cible = [f.name() for f in couche_cible.fields()]
    nouvelles_features = []
    for feature in couche_source.getFeatures():
        nouvelle = QgsFeature(couche_cible.fields())
        nouvelle.setGeometry(feature.geometry())
        for nom in noms_champs_cible:
            if nom in feature.fields().names():
                nouvelle[nom] = feature[nom]
        nouvelles_features.append(nouvelle)
    couche_cible.dataProvider().addFeatures(nouvelles_features)
