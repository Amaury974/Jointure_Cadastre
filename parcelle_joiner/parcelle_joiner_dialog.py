# -*- coding: utf-8 -*-
"""
Boîte de dialogue principale.
Fait le lien entre l'UI (.ui) et la logique métier (core/).
"""
import os

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QMessageBox
from qgis.core import QgsVectorLayer, QgsProject, QgsMapLayerProxyModel

from .core.normalize import normaliser_parcelle
from .core.ftp_loader import charger_couche_cadastrale_ftp, FtpLoadError
from .core.join_processor import executer_jointure

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "parcelle_joiner_dialog_base.ui")
)


class ParcelleJoinerDialog(QDialog, FORM_CLASS):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.couche_table = None       # QgsVectorLayer : tableau de données source
        self.couche_cadastre = None    # QgsVectorLayer : couche de parcelles

        # Restreindre le sélecteur de couche locale aux couches vecteur polygonales
        self.mComboLayerCadastre.setFilters(QgsMapLayerProxyModel.PolygonLayer)

        # Connexions
        self.mFileWidgetTable.fileChanged.connect(self.on_table_selectionnee)
        self.mRadioFtp.toggled.connect(self.on_source_cadastre_changee)
        self.mRadioLocal.toggled.connect(self.on_source_cadastre_changee)
        self.mComboLayerCadastre.layerChanged.connect(self.on_couche_locale_changee)
        self.mButtonApercu.clicked.connect(self.on_apercu_normalisation)
        self.buttonBox.accepted.connect(self.on_lancer_traitement)
        self.buttonBox.rejected.connect(self.reject)

        self.on_source_cadastre_changee()

    # ------------------------------------------------------------------
    # Gestion des changements d'état de l'UI
    # ------------------------------------------------------------------
    def on_table_selectionnee(self, chemin):
        """Charge le tableau et remplit la liste des colonnes disponibles."""
        if not chemin:
            return
        self.couche_table = QgsVectorLayer(chemin, "table_source", "ogr")
        self.mComboColonneNumero.clear()
        if self.couche_table.isValid():
            champs = [f.name() for f in self.couche_table.fields()]
            self.mComboColonneNumero.addItems(champs)
        else:
            self._log("Impossible de charger le fichier tableau sélectionné.")

    def on_source_cadastre_changee(self):
        """Active/désactive le sélecteur de couche locale selon le mode choisi."""
        utiliser_local = self.mRadioLocal.isChecked()
        self.mComboLayerCadastre.setEnabled(utiliser_local)
        if not utiliser_local:
            self.couche_cadastre = None  # sera chargée depuis le FTP au lancement
            self.mComboChampCadastre.clear()
        else:
            self.on_couche_locale_changee(self.mComboLayerCadastre.currentLayer())

    def on_couche_locale_changee(self, couche):
        self.couche_cadastre = couche
        self.mComboChampCadastre.clear()
        if couche is not None:
            self.mComboChampCadastre.addItems([f.name() for f in couche.fields()])

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def on_apercu_normalisation(self):
        """Affiche un avant/après sur quelques valeurs pour validation par l'utilisateur."""
        if self.couche_table is None or not self.couche_table.isValid():
            QMessageBox.warning(self, "Aperçu", "Sélectionnez d'abord un tableau de données.")
            return

        colonne = self.mComboColonneNumero.currentText()
        options = self._options_normalisation()

        lignes = []
        for i, feature in enumerate(self.couche_table.getFeatures()):
            if i >= 10:
                break
            valeur_brute = str(feature[colonne])
            valeur_normalisee = normaliser_parcelle(valeur_brute, **options)
            lignes.append(f"{valeur_brute!r:>20}  ->  {valeur_normalisee!r}")

        self._log("Aperçu de normalisation (10 premières lignes) :")
        self._log("\n".join(lignes))

    def on_lancer_traitement(self):
        """Point d'entrée du traitement complet : chargement cadastre, normalisation, jointure."""
        try:
            if self.mRadioFtp.isChecked():
                self._log("Téléchargement de la couche cadastrale depuis le serveur FTP...")
                self.couche_cadastre = charger_couche_cadastrale_ftp(
                    progress_callback=self.mProgressBar.setValue
                )
                self.mComboChampCadastre.clear()
                self.mComboChampCadastre.addItems(
                    [f.name() for f in self.couche_cadastre.fields()]
                )

            if self.couche_cadastre is None or not self.couche_cadastre.isValid():
                raise ValueError("Aucune couche cadastrale valide n'est disponible.")

            if self.couche_table is None or not self.couche_table.isValid():
                raise ValueError("Aucun tableau de données valide n'est sélectionné.")

            colonne_table = self.mComboColonneNumero.currentText()
            champ_cadastre = self.mComboChampCadastre.currentText()
            options = self._options_normalisation()

            self._log("Lancement de la jointure...")
            couche_resultat, rapport = executer_jointure(
                couche_table=self.couche_table,
                colonne_table=colonne_table,
                couche_cadastre=self.couche_cadastre,
                champ_cadastre=champ_cadastre,
                options_normalisation=options,
                progress_callback=self.mProgressBar.setValue,
            )

            QgsProject.instance().addMapLayer(couche_resultat)

            self._log(
                f"Terminé : {rapport['nb_trouves']} parcelle(s) trouvée(s), "
                f"{rapport['nb_non_trouves']} non trouvée(s), "
                f"{rapport['nb_doublons']} doublon(s) détecté(s)."
            )
            if rapport["nb_non_trouves"]:
                self._log("Numéros non trouvés : " + ", ".join(rapport["non_trouves"][:20]))

        except FtpLoadError as e:
            QMessageBox.critical(
                self, "Erreur FTP",
                f"Impossible de récupérer la couche depuis le serveur FTP :\n{e}\n\n"
                "Sélectionnez 'Utiliser ma propre couche cadastrale' pour continuer."
            )
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------
    def _options_normalisation(self):
        return {
            "supprimer_separateurs": self.mCheckSupprEspaces.isChecked(),
            "majuscules": self.mCheckMajuscules.isChecked(),
            "padding": self.mCheckPadding.isChecked(),
        }

    def _log(self, message):
        self.mLogOutput.appendPlainText(message)
