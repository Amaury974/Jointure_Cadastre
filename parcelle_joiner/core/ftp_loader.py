# -*- coding: utf-8 -*-
"""
Récupération de la couche de parcelles cadastrales de référence depuis un serveur FTP.

Stratégie :
    1. Se connecter au FTP et télécharger le fichier (ex: GeoPackage ou shapefile zippé)
       vers un dossier de cache local.
    2. Ne pas retélécharger si une copie locale récente existe déjà (cache simple basé
       sur la date de dernière modification distante, quand le serveur l'expose).
    3. Charger le résultat avec QgsVectorLayer.

Adaptez FTP_HOST / FTP_CHEMIN_DISTANT / FTP_IDENTIFIANTS à votre infrastructure.
Pour un serveur interne à l'organisation, ces valeurs peuvent être en dur ici ;
pour un usage plus général, préférez les stocker via QSettings et les rendre
configurables dans un onglet "Paramètres" du plugin.
"""
import ftplib
import os
import tempfile
import time

from qgis.core import QgsVectorLayer

FTP_HOST = "ftp.exemple.fr"
FTP_PORT = 21
FTP_USER = "utilisateur"
FTP_PASSWORD = "mot_de_passe"
FTP_CHEMIN_DISTANT = "/donnees/cadastre/parcelles.gpkg"

# Dossier de cache local (persistant entre deux sessions QGIS)
CACHE_DIR = os.path.join(tempfile.gettempdir(), "parcelle_joiner_cache")
CACHE_MAX_AGE_SECONDES = 24 * 3600  # on ne retélécharge pas si le cache a moins de 24h


class FtpLoadError(Exception):
    """Erreur levée lorsque la couche cadastrale ne peut pas être récupérée depuis le FTP."""
    pass


def charger_couche_cadastrale_ftp(progress_callback=None):
    """
    Télécharge (si besoin) et charge la couche cadastrale de référence.

    :param progress_callback: fonction optionnelle appelée avec un pourcentage (0-100)
    :return: QgsVectorLayer valide
    :raises FtpLoadError: si le téléchargement ou le chargement échoue
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    nom_fichier = os.path.basename(FTP_CHEMIN_DISTANT)
    chemin_local = os.path.join(CACHE_DIR, nom_fichier)

    if _cache_valide(chemin_local):
        if progress_callback:
            progress_callback(100)
        return _charger_depuis_fichier(chemin_local)

    try:
        _telecharger_ftp(chemin_local, progress_callback)
    except (ftplib.all_errors, OSError) as e:
        raise FtpLoadError(str(e)) from e

    return _charger_depuis_fichier(chemin_local)


def _cache_valide(chemin_local):
    if not os.path.exists(chemin_local):
        return False
    age = time.time() - os.path.getmtime(chemin_local)
    return age < CACHE_MAX_AGE_SECONDES


def _telecharger_ftp(chemin_local, progress_callback=None):
    with ftplib.FTP() as ftp:
        ftp.connect(FTP_HOST, FTP_PORT, timeout=30)
        ftp.login(FTP_USER, FTP_PASSWORD)

        taille_totale = ftp.size(FTP_CHEMIN_DISTANT) or 0
        recu = {"octets": 0}

        chemin_temp = chemin_local + ".tmp"
        with open(chemin_temp, "wb") as f:
            def callback_ecriture(bloc):
                f.write(bloc)
                recu["octets"] += len(bloc)
                if progress_callback and taille_totale:
                    pourcentage = int(recu["octets"] * 100 / taille_totale)
                    progress_callback(min(pourcentage, 100))

            ftp.retrbinary(f"RETR {FTP_CHEMIN_DISTANT}", callback_ecriture)

        os.replace(chemin_temp, chemin_local)


def _charger_depuis_fichier(chemin_local):
    couche = QgsVectorLayer(chemin_local, "parcelles_cadastrales", "ogr")
    if not couche.isValid():
        raise FtpLoadError(f"Le fichier téléchargé n'est pas une couche valide : {chemin_local}")
    return couche
