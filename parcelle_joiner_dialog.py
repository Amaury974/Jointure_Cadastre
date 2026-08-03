# -*- coding: utf-8 -*-
"""
Boîte de dialogue principale.
Fait le lien entre l'UI (.ui) et la logique métier (core/).
"""
import os
from itertools import groupby

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QMessageBox
from qgis.core import QgsProject, QgsMapLayerProxyModel

from .core.table_reader import ouvrir_table_source, lister_feuilles, TableSourceError
from .core.column_detector import detecter_roles_colonnes
from .core.row_expander import preparer_lignes_depuis_features
from .core.ftp_loader import charger_couche_cadastrale_ftp, FtpLoadError
from .core.cadastre_source import charger_couche_cadastre_communes, CadastreSourceError
from .core.join_processor import preparer_lignes_table, codes_insee_necessaires, joindre_avec_cadastre
from .ftp_settings_dialog import FtpSettingsDialog

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "parcelle_joiner_dialog_base.ui")
)

EXTENSIONS_MULTI_FEUILLES = (".xlsx", ".xls", ".ods")
FILTRE_FICHIERS = (
    "Tableaux (*.csv *.xlsx *.xls *.ods);;"
    "CSV (*.csv);;Excel (*.xlsx *.xls);;OpenDocument (*.ods);;Tous les fichiers (*.*)"
)


class ParcelleJoinerDialog(QDialog, FORM_CLASS):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.couche_table = None       # QgsVectorLayer : tableau de données source
        self.couche_cadastre = None    # QgsVectorLayer : couche de parcelles
        self.chemin_table_courant = None

        self.mFileWidgetTable.setFilter(FILTRE_FICHIERS)
        self.mComboLayerCadastre.setFilters(QgsMapLayerProxyModel.PolygonLayer)

        # Connexions
        self.mFileWidgetTable.fileChanged.connect(self.on_fichier_selectionne)
        self.mComboFeuille.currentTextChanged.connect(self.on_feuille_changee)
        self.mButtonDetecter.clicked.connect(self.on_detecter_colonnes)
        for radio in (self.mRadioModeSepare, self.mRadioModeCombine, self.mRadioModeToutEnUn):
            radio.toggled.connect(self.on_mode_colonnes_change)
        self.mRadioAuto.toggled.connect(self.on_source_cadastre_changee)
        self.mRadioFtp.toggled.connect(self.on_source_cadastre_changee)
        self.mRadioLocal.toggled.connect(self.on_source_cadastre_changee)
        self.mComboLayerCadastre.layerChanged.connect(self.on_couche_locale_changee)
        self.mButtonParametresFtp.clicked.connect(self.on_ouvrir_parametres_ftp)
        self.mButtonApercu.clicked.connect(self.on_apercu_traitement)
        self.buttonBox.accepted.connect(self.on_lancer_traitement)
        self.buttonBox.rejected.connect(self.reject)

        self.on_mode_colonnes_change()
        self.on_source_cadastre_changee()

    # ------------------------------------------------------------------
    # Chargement du tableau source (CSV / XLSX / ODS)
    # ------------------------------------------------------------------
    def on_fichier_selectionne(self, chemin):
        if not chemin:
            return
        self.chemin_table_courant = chemin
        extension = os.path.splitext(chemin)[1].lower()

        self.mComboFeuille.blockSignals(True)
        self.mComboFeuille.clear()
        if extension in EXTENSIONS_MULTI_FEUILLES:
            feuilles = lister_feuilles(chemin)
            self.mComboFeuille.addItems(feuilles)
            self.mComboFeuille.setEnabled(bool(feuilles))
        else:
            self.mComboFeuille.setEnabled(False)
        self.mComboFeuille.blockSignals(False)

        self._charger_table(chemin, self.mComboFeuille.currentText() or None)

    def on_feuille_changee(self, nom_feuille):
        if self.chemin_table_courant and nom_feuille:
            self._charger_table(self.chemin_table_courant, nom_feuille)

    def _charger_table(self, chemin, nom_feuille):
        try:
            self.couche_table = ouvrir_table_source(chemin, nom_feuille)
        except TableSourceError as e:
            QMessageBox.warning(self, "Erreur de lecture", str(e))
            self.couche_table = None
            return

        self._rafraichir_listes_colonnes()
        self.on_detecter_colonnes()

    def _rafraichir_listes_colonnes(self):
        if self.couche_table is None:
            return
        noms_champs = [f.name() for f in self.couche_table.fields()]
        for combo in (
            self.mComboColCommune, self.mComboColParcelleCombinee,
            self.mComboColSection, self.mComboColNumero,
        ):
            valeur_actuelle = combo.currentText()
            combo.clear()
            combo.addItems([""] + noms_champs)
            index = combo.findText(valeur_actuelle)
            if index >= 0:
                combo.setCurrentIndex(index)

    # ------------------------------------------------------------------
    # Détection automatique / choix du mode de colonnes
    # ------------------------------------------------------------------
    def on_detecter_colonnes(self):
        if self.couche_table is None or not self.couche_table.isValid():
            return

        from .core.table_reader import extraire_echantillon, classifier_types_champs
        echantillon = extraire_echantillon(self.couche_table)
        types_colonnes = classifier_types_champs(self.couche_table)
        config = detecter_roles_colonnes(echantillon, types_colonnes=types_colonnes)

        mode_vers_radio = {
            "colonnes_separees": self.mRadioModeSepare,
            "section_numero_ensemble": self.mRadioModeCombine,
            "tout_en_un": self.mRadioModeToutEnUn,
        }
        mode_vers_radio.get(config["mode"], self.mRadioModeCombine).setChecked(True)

        self._selectionner_combo(self.mComboColCommune, config["colonne_commune"])
        self._selectionner_combo(self.mComboColParcelleCombinee, config["colonne_parcelle_combinee"])
        self._selectionner_combo(self.mComboColSection, config["colonne_section"])
        self._selectionner_combo(self.mComboColNumero, config["colonne_numero"])

        self._log(f"Détection automatique : mode = {config['mode']!r}.")

    def _selectionner_combo(self, combo, valeur):
        if valeur is None:
            combo.setCurrentIndex(0)
            return
        index = combo.findText(valeur)
        if index >= 0:
            combo.setCurrentIndex(index)

    def on_mode_colonnes_change(self):
        mode_separe = self.mRadioModeSepare.isChecked()
        mode_tout_en_un = self.mRadioModeToutEnUn.isChecked()

        self.mComboColParcelleCombinee.setEnabled(not mode_separe and not mode_tout_en_un)
        self.labelColParcelleCombinee.setEnabled(not mode_separe and not mode_tout_en_un)
        self.mComboColSection.setEnabled(mode_separe)
        self.labelColSection.setEnabled(mode_separe)
        self.mComboColNumero.setEnabled(mode_separe)
        self.labelColNumero.setEnabled(mode_separe)
        # En mode "tout en un", la colonne "commune" EST la colonne combinée
        self.mComboColCommune.setEnabled(True)
        self.labelColCommune.setEnabled(True)

    def _config_colonnes_actuelle(self):
        if self.mRadioModeSepare.isChecked():
            mode = "colonnes_separees"
        elif self.mRadioModeToutEnUn.isChecked():
            mode = "tout_en_un"
        else:
            mode = "section_numero_ensemble"

        return {
            "mode": mode,
            "colonne_commune": self.mComboColCommune.currentText() or None,
            "colonne_parcelle_combinee": self.mComboColParcelleCombinee.currentText() or None,
            "colonne_section": self.mComboColSection.currentText() or None,
            "colonne_numero": self.mComboColNumero.currentText() or None,
        }

    # ------------------------------------------------------------------
    # Cadastre : FTP ou couche locale
    # ------------------------------------------------------------------
    def on_source_cadastre_changee(self):
        utiliser_local = self.mRadioLocal.isChecked()
        self.mComboLayerCadastre.setEnabled(utiliser_local)
        # Champ cadastral : fixé à "id" pour la récupération auto (schéma Etalab connu),
        # laissé au choix de l'utilisateur pour le FTP / la couche locale.
        self.mComboChampCadastre.setEnabled(not self.mRadioAuto.isChecked())
        if self.mRadioAuto.isChecked():
            self.couche_cadastre = None
            self.mComboChampCadastre.clear()
            self.mComboChampCadastre.addItem("id")
        elif utiliser_local:
            self.on_couche_locale_changee(self.mComboLayerCadastre.currentLayer())
        else:
            self.couche_cadastre = None  # sera chargée depuis le FTP au lancement
            self.mComboChampCadastre.clear()

    def on_couche_locale_changee(self, couche):
        self.couche_cadastre = couche
        self.mComboChampCadastre.clear()
        if couche is not None:
            self.mComboChampCadastre.addItems([f.name() for f in couche.fields()])

    def on_ouvrir_parametres_ftp(self):
        dlg = FtpSettingsDialog(self)
        dlg.exec_()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def on_apercu_traitement(self):
        """
        Affiche un aperçu groupé par ligne source : la valeur telle que
        saisie dans le tableau d'origine (commune + section/numéro brut) est
        affichée une seule fois, suivie du/des résultat(s) normalisé(s).
        Une ligne source contenant plusieurs parcelles produit plusieurs
        résultats sous la même entrée brute (duplication).
        """
        if self.couche_table is None or not self.couche_table.isValid():
            QMessageBox.warning(self, "Aperçu", "Sélectionnez d'abord un tableau de données.")
            return

        config = self._config_colonnes_actuelle()
        options = self._options_normalisation()

        noms_champs = [f.name() for f in self.couche_table.fields()]
        lignes = []
        for i, feature in enumerate(self.couche_table.getFeatures()):
            if i >= 15:
                break
            lignes.append({nom: feature[nom] for nom in noms_champs})

        resultats = preparer_lignes_depuis_features(lignes, config, options)

        self._log("Aperçu du traitement (15 premières lignes source) :")
        for _, groupe in groupby(resultats, key=lambda r: r["index_ligne_source"]):
            groupe = list(groupe)
            premier = groupe[0]

            valeur_brute_parcelle = self._valeur_brute_parcelle(premier["attributs_originaux"], config)
            if config["mode"] == "tout_en_un":
                ligne_brute = str(premier["commune_brute"])
            else:
                ligne_brute = f"{premier['commune_brute']} ; {valeur_brute_parcelle}"

            avert = f"  ⚠ {' | '.join(premier['avertissements'])}" if premier["avertissements"] else ""
            self._log(f"{ligne_brute}{avert}")

            for r in groupe:
                parties = [r['nom_commune'] or '?', r['section'], r['numero']]
                resultat = " ".join(p for p in parties if p)
                self._log(f"  ->  {resultat}   [{r['code_parcelle_normalise']}]")

    def _valeur_brute_parcelle(self, attributs, config):
        """Reconstruit la valeur 'section+numéro' telle que saisie dans les colonnes d'origine."""
        if config["mode"] == "colonnes_separees":
            section = attributs.get(config["colonne_section"], "")
            numero = attributs.get(config["colonne_numero"], "")
            return f"{section} {numero}".strip()
        return str(attributs.get(config["colonne_parcelle_combinee"], ""))

    def on_lancer_traitement(self):
        """
        Point d'entrée du traitement complet, en 2 temps :
          1. Préparation des lignes du tableau source (identification commune,
             découpage des parcelles) — indépendante du cadastre.
          2. Récupération de la couche cadastrale adaptée à la source choisie
             (auto : uniquement les communes nécessaires ; FTP : couche de
             référence complète ; locale : couche fournie par l'utilisateur),
             puis jointure.
        """
        try:
            if self.couche_table is None or not self.couche_table.isValid():
                raise ValueError("Aucun tableau de données valide n'est sélectionné.")

            config_colonnes = self._config_colonnes_actuelle()
            if not config_colonnes["colonne_commune"]:
                raise ValueError("Veuillez sélectionner la colonne contenant la commune.")

            options = self._options_normalisation()

            self._log("Préparation des lignes (identification des communes, découpage des parcelles)...")
            lignes_preparees = preparer_lignes_table(self.couche_table, config_colonnes, options)
            champs_table = self.couche_table.fields()

            if self.mRadioAuto.isChecked():
                codes = codes_insee_necessaires(lignes_preparees)
                if not codes:
                    raise ValueError(
                        "Aucune commune n'a pu être identifiée dans le tableau source : "
                        "impossible de savoir quelles communes récupérer."
                    )
                self._log(
                    f"Récupération automatique de {len(codes)} commune(s) depuis "
                    "cadastre.data.gouv.fr..."
                )
                self.couche_cadastre, communes_en_echec = charger_couche_cadastre_communes(
                    codes, progress_callback=self.mProgressBar.setValue
                )
                if communes_en_echec:
                    self._log(
                        f"⚠ {len(communes_en_echec)} commune(s) n'ont pas pu être récupérées : "
                        + ", ".join(f"{c} ({m})" for c, m in communes_en_echec.items())
                    )
                champ_cadastre = "id"

            elif self.mRadioFtp.isChecked():
                self._log("Téléchargement de la couche cadastrale depuis le serveur FTP...")
                self.couche_cadastre = charger_couche_cadastrale_ftp(
                    progress_callback=self.mProgressBar.setValue
                )
                champ_cadastre = self.mComboChampCadastre.currentText()

            else:
                champ_cadastre = self.mComboChampCadastre.currentText()

            if self.couche_cadastre is None or not self.couche_cadastre.isValid():
                raise ValueError("Aucune couche cadastrale valide n'est disponible.")
            if not champ_cadastre:
                raise ValueError("Veuillez sélectionner le champ 'numéro de parcelle' du cadastre.")

            self._log("Lancement de la jointure...")
            couche_resultat, couche_non_reconnues, rapport = joindre_avec_cadastre(
                lignes_preparees=lignes_preparees,
                champs_table=champs_table,
                couche_cadastre=self.couche_cadastre,
                champ_cadastre=champ_cadastre,
                options_normalisation=options,
                progress_callback=self.mProgressBar.setValue,
            )

            QgsProject.instance().addMapLayer(couche_resultat)
            if couche_non_reconnues.featureCount() > 0:
                QgsProject.instance().addMapLayer(couche_non_reconnues)

            self._log(
                f"Terminé : {rapport['nb_lignes_source']} ligne(s) source, "
                f"{rapport['nb_parcelles_total']} parcelle(s) au total "
                f"({rapport['nb_lignes_dupliquees']} ligne(s) dupliquée(s) car "
                f"contenant plusieurs parcelles).\n"
                f"  -> {rapport['nb_trouves']} trouvée(s), "
                f"{rapport['nb_non_trouves']} non trouvée(s) (ajoutée(s) à la table "
                f"'parcelles_non_reconnues'), "
                f"{rapport['nb_doublons_cadastre']} doublon(s) cadastre, "
                f"{rapport['nb_commune_non_reconnue']} commune(s) non reconnue(s)."
            )
            if rapport["nb_non_trouves"]:
                self._log("Numéros non trouvés : " + ", ".join(str(v) for v in rapport["non_trouves"][:20]))

        except (FtpLoadError, CadastreSourceError) as e:
            QMessageBox.critical(
                self, "Erreur de récupération du cadastre",
                f"{e}\n\nVous pouvez essayer une autre source (couche locale, FTP...)."
            )
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------
    def _options_normalisation(self):
        return {
            "majuscules": self.mCheckMajuscules.isChecked(),
            "padding": self.mCheckPadding.isChecked(),
        }

    def _log(self, message):
        self.mLogOutput.appendPlainText(message)
