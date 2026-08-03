# -*- coding: utf-8 -*-
"""
Paramètres persistants du plugin.

Deux mécanismes de stockage distincts, choisis selon la sensibilité des
données :
    - QSettings (fichier .ini / registre, NON chiffré) pour les informations
      non sensibles : hôte, port, chemin du fichier distant.
    - Le gestionnaire d'authentification de QGIS (QgsAuthManager, base
      CHIFFRÉE protégée par un mot de passe maître) pour les identifiants
      (utilisateur/mot de passe). Seul l'identifiant de la configuration
      d'authentification ("authcfg", une chaîne de 7 caractères générée par
      QGIS) est stocké dans QSettings — jamais le mot de passe lui-même.

Ce découpage est le mécanisme standard utilisé par les fournisseurs de
données intégrés à QGIS (WFS, PostgreSQL, etc.) via le widget
QgsAuthConfigSelect (voir ftp_settings_dialog.py).
"""
from qgis.PyQt.QtCore import QSettings

GROUPE = "ParcelleJoiner"

CLE_HOST = "ftp_host"
CLE_PORT = "ftp_port"
CLE_AUTHCFG = "ftp_authcfg"
CLE_CHEMIN_DISTANT = "ftp_chemin_distant"

PORT_PAR_DEFAUT = 21


def _settings():
    return QSettings()


def obtenir_parametres_ftp():
    """Retourne un dict {host, port, authcfg, chemin_distant} depuis QSettings."""
    s = _settings()
    s.beginGroup(GROUPE)
    parametres = {
        "host": s.value(CLE_HOST, "", type=str),
        "port": s.value(CLE_PORT, PORT_PAR_DEFAUT, type=int),
        "authcfg": s.value(CLE_AUTHCFG, "", type=str),
        "chemin_distant": s.value(CLE_CHEMIN_DISTANT, "", type=str),
    }
    s.endGroup()
    return parametres


def enregistrer_parametres_ftp(host, port, authcfg, chemin_distant):
    """Enregistre durablement les paramètres FTP saisis par l'utilisateur."""
    s = _settings()
    s.beginGroup(GROUPE)
    s.setValue(CLE_HOST, host)
    s.setValue(CLE_PORT, port)
    s.setValue(CLE_AUTHCFG, authcfg)
    s.setValue(CLE_CHEMIN_DISTANT, chemin_distant)
    s.endGroup()
    s.sync()


def parametres_ftp_configures():
    """True si le minimum requis (serveur + chemin du fichier) est renseigné.
    L'authcfg peut rester vide (cas d'un serveur FTP anonyme)."""
    p = obtenir_parametres_ftp()
    return bool(p["host"]) and bool(p["chemin_distant"])


def obtenir_identifiants_authcfg(authcfg):
    """
    Résout un identifiant de configuration d'authentification QGIS
    (authcfg) en un couple (utilisateur, mot_de_passe), en interrogeant le
    gestionnaire d'authentification de QGIS.

    :param authcfg: identifiant de la configuration (ex: "a1b2c3d"), ou
        chaîne vide pour une connexion anonyme.
    :return: (utilisateur: str, mot_de_passe: str) — ("", "") si authcfg vide.
    :raises ValueError: si la configuration référencée est introuvable ou
        n'a pas pu être déchiffrée (mot de passe maître non déverrouillé,
        configuration corrompue, etc.)
    """
    if not authcfg:
        return "", ""

    from qgis.core import QgsApplication, QgsAuthMethodConfig

    config = QgsAuthMethodConfig()
    gestionnaire = QgsApplication.authManager()
    succes = gestionnaire.loadAuthenticationConfig(authcfg, config, True)  # True = déchiffre les champs sensibles

    if not succes or not config.isValid():
        raise ValueError(
            f"Impossible de charger la configuration d'authentification {authcfg!r}. "
            "Vérifiez qu'elle existe toujours (Préférences > Authentification) et que "
            "le mot de passe maître de QGIS a bien été déverrouillé."
        )

    utilisateur = config.config("username", "")
    mot_de_passe = config.config("password", "")
    return utilisateur, mot_de_passe
