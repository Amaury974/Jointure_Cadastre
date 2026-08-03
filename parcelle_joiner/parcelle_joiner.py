# -*- coding: utf-8 -*-
"""
Classe principale du plugin.
Gère l'intégration à l'interface QGIS (menu, barre d'outils)
et l'ouverture de la boîte de dialogue.
"""
import os

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .parcelle_joiner_dialog import ParcelleJoinerDialog


class ParcelleJoinerPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = "&Parcelle Joiner"
        self.toolbar = self.iface.addToolBar("ParcelleJoiner")
        self.toolbar.setObjectName("ParcelleJoiner")
        self.dlg = None

        # Traductions (optionnel, à compléter si besoin de i18n)
        locale = QSettings().value("locale/userLocale", "fr")[0:2]
        locale_path = os.path.join(self.plugin_dir, "i18n", f"parcelle_joiner_{locale}.qm")
        self.translator = None
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, "icon.png")
        action = QAction(QIcon(icon_path), "Joindre parcelles cadastrales", self.iface.mainWindow())
        action.triggered.connect(self.run)
        action.setEnabled(True)

        self.toolbar.addAction(action)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    def run(self):
        """Ouvre (ou réutilise) la boîte de dialogue principale."""
        if self.dlg is None:
            self.dlg = ParcelleJoinerDialog(self.iface.mainWindow())
        self.dlg.show()
        self.dlg.exec_()
