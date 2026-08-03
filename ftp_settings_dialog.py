# -*- coding: utf-8 -*-
"""
Boîte de dialogue permettant à l'utilisateur de saisir/modifier les
paramètres de connexion au serveur FTP hébergeant la couche cadastrale de
référence.

Les identifiants (utilisateur/mot de passe) sont gérés par le système
d'authentification de QGIS (QgsAuthConfigSelect + QgsAuthManager) — base
chiffrée, protégée par le mot de passe maître de QGIS — plutôt que stockés
en clair par le plugin. Seuls l'hôte, le port et le chemin du fichier
distant (non sensibles) sont enregistrés via QSettings (core/settings.py).
"""
import os

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QMessageBox

from .core.settings import obtenir_parametres_ftp, enregistrer_parametres_ftp
from .core.ftp_loader import tester_connexion_ftp

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "ftp_settings_dialog_base.ui")
)


class FtpSettingsDialog(QDialog, FORM_CLASS):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        parametres = obtenir_parametres_ftp()
        self.mLineHost.setText(parametres["host"])
        self.mSpinPort.setValue(parametres["port"])
        self.mAuthConfigSelect.setConfigId(parametres["authcfg"])
        self.mLineCheminDistant.setText(parametres["chemin_distant"])

        self.mButtonTester.clicked.connect(self.on_tester_connexion)
        self.buttonBox.accepted.connect(self.on_enregistrer)
        self.buttonBox.rejected.connect(self.reject)

    def on_tester_connexion(self):
        self.mLabelResultatTest.setText("Test en cours...")
        succes, message = tester_connexion_ftp(
            host=self.mLineHost.text().strip(),
            port=self.mSpinPort.value(),
            authcfg=self.mAuthConfigSelect.configId(),
            chemin_distant=self.mLineCheminDistant.text().strip(),
        )
        couleur = "green" if succes else "red"
        self.mLabelResultatTest.setText(f"<span style='color:{couleur}'>{message}</span>")

    def on_enregistrer(self):
        host = self.mLineHost.text().strip()
        chemin_distant = self.mLineCheminDistant.text().strip()

        if not host or not chemin_distant:
            QMessageBox.warning(
                self, "Paramètres incomplets",
                "Le serveur et le chemin du fichier distant sont obligatoires."
            )
            return

        enregistrer_parametres_ftp(
            host=host,
            port=self.mSpinPort.value(),
            authcfg=self.mAuthConfigSelect.configId(),
            chemin_distant=chemin_distant,
        )
        self.accept()
