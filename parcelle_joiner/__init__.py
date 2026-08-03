# -*- coding: utf-8 -*-
"""
Point d'entrée du plugin QGIS.
QGIS appelle classFactory() pour instancier le plugin.
"""


def classFactory(iface):
    from .parcelle_joiner import ParcelleJoinerPlugin
    return ParcelleJoinerPlugin(iface)
