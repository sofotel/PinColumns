# -*- coding: utf-8 -*-
"""Point d'entree vu par QGIS. Charge la classe du plugin."""


def classFactory(iface):
    """Charge la classe PinColumns.

    :param iface: interface QGIS
    :type iface: QgsInterface
    """
    from .pincolumns import PinColumns
    return PinColumns(iface)
