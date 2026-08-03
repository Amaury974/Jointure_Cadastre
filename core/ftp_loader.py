# -*- coding: utf-8 -*-
"""
Récupération de la couche de parcelles cadastrales de référence depuis un
serveur FTP dont les paramètres sont configurés par l'utilisateur via
QSettings (voir core/settings.py et ftp_settings_dialog.py — accessible
depuis le menu du plugin : "Paramètres FTP...").

Le fichier distant peut être :
    - un shapefile (.shp) : dans ce cas, tous les fichiers annexes partageant
      le même nom de base (.shx, .dbf, .prj, ...) sont aussi téléchargés,
      car un .shp seul n'est pas exploitable par QGIS ;
    - tout autre format lisible par OGR en un seul fichier (GeoJSON,
      GeoPackage, ...) : un seul fichier est alors téléchargé.
Le format est déduit automatiquement de l'extension du chemin distant
configuré.
"""
import ftplib
import os
import posixpath
import tempfile
import time

EXTENSIONS_SHAPEFILE = (
    ".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx", ".qix", ".fbn", ".fbx",
)

CACHE_DIR = os.path.join(tempfile.gettempdir(), "parcelle_joiner_cache")
CACHE_MAX_AGE_SECONDES = 24 * 3600  # on ne retélécharge pas si le cache a moins de 24h


class FtpLoadError(Exception):
    """Erreur levée lorsque la couche cadastrale ne peut pas être récupérée depuis le FTP."""
    pass


def est_shapefile(chemin_distant):
    """Détermine, à partir de l'extension, si le chemin distant pointe vers un shapefile."""
    return posixpath.splitext(chemin_distant)[1].lower() == ".shp"


def charger_couche_cadastrale_ftp(progress_callback=None):
    """
    Télécharge (si besoin, sinon utilise le cache local) et charge la couche
    cadastrale de référence, à partir des paramètres FTP enregistrés par
    l'utilisateur.

    :param progress_callback: fonction optionnelle appelée avec un pourcentage (0-100)
    :return: QgsVectorLayer valide
    :raises FtpLoadError: si aucun paramètre n'est configuré, ou si le
        téléchargement/chargement échoue
    """
    from .settings import obtenir_parametres_ftp, parametres_ftp_configures

    if not parametres_ftp_configures():
        raise FtpLoadError(
            "Aucun serveur FTP n'est configuré. Ouvrez le menu "
            "'Extensions > Parcelle Joiner > Paramètres FTP...' pour renseigner "
            "l'adresse du serveur et le chemin du fichier cadastral à récupérer."
        )

    parametres = obtenir_parametres_ftp()
    chemin_distant = parametres["chemin_distant"]

    os.makedirs(CACHE_DIR, exist_ok=True)
    nom_fichier = posixpath.basename(chemin_distant)
    chemin_local = os.path.join(CACHE_DIR, nom_fichier)

    if _cache_valide(chemin_local):
        if progress_callback:
            progress_callback(100)
        return _charger_depuis_fichier(chemin_local)

    try:
        if est_shapefile(chemin_distant):
            dossier_distant = posixpath.dirname(chemin_distant)
            nom_base = posixpath.splitext(nom_fichier)[0]
            _telecharger_shapefile_ftp(parametres, dossier_distant, nom_base, progress_callback)
        else:
            _telecharger_fichier_unique_ftp(parametres, chemin_distant, chemin_local, progress_callback)
    except (ftplib.all_errors, OSError) as e:
        raise FtpLoadError(str(e)) from e

    return _charger_depuis_fichier(chemin_local)


def _cache_valide(chemin_local):
    if not os.path.exists(chemin_local):
        return False
    age = time.time() - os.path.getmtime(chemin_local)
    return age < CACHE_MAX_AGE_SECONDES


def _connexion_ftp(parametres):
    from .settings import obtenir_identifiants_authcfg

    utilisateur, mot_de_passe = obtenir_identifiants_authcfg(parametres["authcfg"])

    ftp = ftplib.FTP()
    ftp.connect(parametres["host"], parametres["port"] or 21, timeout=30)
    if utilisateur or mot_de_passe:
        ftp.login(utilisateur, mot_de_passe)
    else:
        ftp.login()  # connexion anonyme
    return ftp


def _lister_fichiers_associes(ftp, dossier_distant, nom_base):
    """
    Liste, dans le dossier distant, tous les fichiers partageant le nom de
    base du shapefile (quelle que soit l'extension), en se limitant aux
    extensions connues d'un shapefile.
    """
    noms = ftp.nlst(dossier_distant)
    fichiers = []
    for chemin in noms:
        nom_fichier = posixpath.basename(chemin)
        base, ext = posixpath.splitext(nom_fichier)
        if base.lower() == nom_base.lower() and ext.lower() in EXTENSIONS_SHAPEFILE:
            fichiers.append(chemin)
    return fichiers


def _telecharger_shapefile_ftp(parametres, dossier_distant, nom_base, progress_callback=None):
    with _connexion_ftp(parametres) as ftp:
        fichiers_distants = _lister_fichiers_associes(ftp, dossier_distant, nom_base)
        if not fichiers_distants:
            raise FtpLoadError(
                f"Aucun fichier trouvé pour le shapefile {nom_base!r} "
                f"dans {dossier_distant!r} sur le serveur FTP."
            )
        if not any(f.lower().endswith(".shp") for f in fichiers_distants):
            raise FtpLoadError(
                f"Le fichier .shp est introuvable pour {nom_base!r} dans {dossier_distant!r}."
            )

        total_fichiers = len(fichiers_distants)
        for i, chemin_distant in enumerate(fichiers_distants):
            nom_fichier = posixpath.basename(chemin_distant)
            chemin_local = os.path.join(CACHE_DIR, nom_fichier)
            chemin_temp = chemin_local + ".tmp"

            with open(chemin_temp, "wb") as f:
                ftp.retrbinary(f"RETR {chemin_distant}", f.write)
            os.replace(chemin_temp, chemin_local)

            if progress_callback:
                progress_callback(int((i + 1) * 100 / total_fichiers))


def _telecharger_fichier_unique_ftp(parametres, chemin_distant, chemin_local, progress_callback=None):
    with _connexion_ftp(parametres) as ftp:
        taille_totale = 0
        try:
            taille_totale = ftp.size(chemin_distant) or 0
        except ftplib.all_errors:
            pass  # certains serveurs FTP ne supportent pas la commande SIZE

        recu = {"octets": 0}
        chemin_temp = chemin_local + ".tmp"
        with open(chemin_temp, "wb") as f:
            def callback_ecriture(bloc):
                f.write(bloc)
                recu["octets"] += len(bloc)
                if progress_callback and taille_totale:
                    progress_callback(min(int(recu["octets"] * 100 / taille_totale), 100))

            ftp.retrbinary(f"RETR {chemin_distant}", callback_ecriture)
        os.replace(chemin_temp, chemin_local)

        if progress_callback:
            progress_callback(100)


def tester_connexion_ftp(host, port, authcfg, chemin_distant):
    """
    Teste une connexion FTP avec les paramètres fournis, sans rien télécharger
    (utilisé par le bouton "Tester la connexion" de la boîte de dialogue des
    paramètres). Les identifiants sont résolus depuis le gestionnaire
    d'authentification de QGIS à partir de `authcfg`.

    :return: (succes: bool, message: str)
    """
    from .settings import obtenir_identifiants_authcfg

    try:
        utilisateur, mot_de_passe = obtenir_identifiants_authcfg(authcfg)
    except ValueError as e:
        return False, str(e)

    dossier_distant = posixpath.dirname(chemin_distant) or "/"
    nom_fichier = posixpath.basename(chemin_distant)
    try:
        with ftplib.FTP() as ftp:
            ftp.connect(host, port or 21, timeout=15)
            if utilisateur or mot_de_passe:
                ftp.login(utilisateur, mot_de_passe)
            else:
                ftp.login()
            noms = ftp.nlst(dossier_distant)
    except ftplib.all_errors as e:
        return False, f"Échec de connexion : {e}"
    except OSError as e:
        return False, f"Erreur réseau : {e}"

    noms_fichiers = [posixpath.basename(n) for n in noms]
    if nom_fichier and nom_fichier not in noms_fichiers:
        # Pour un shapefile, le .shp exact peut différer légèrement en casse : vérif souple
        if not any(n.lower() == nom_fichier.lower() for n in noms_fichiers):
            return True, (
                f"Connexion réussie, mais le fichier {nom_fichier!r} n'a pas été trouvé "
                f"dans {dossier_distant!r}. Vérifiez le chemin."
            )
    return True, f"Connexion réussie : {len(noms_fichiers)} fichier(s) trouvé(s) dans {dossier_distant!r}."


def _charger_depuis_fichier(chemin_local):
    from qgis.core import QgsVectorLayer

    couche = QgsVectorLayer(chemin_local, "parcelles_cadastrales", "ogr")
    if not couche.isValid():
        raise FtpLoadError(f"Le fichier téléchargé n'est pas une couche valide : {chemin_local}")
    return couche
