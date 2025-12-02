from qgis.gui import QgisInterface

from .sdu_agro_tools import SDUAgroTools


def classFactory(iface: QgisInterface) -> SDUAgroTools:
    """Load AgroTool_ColorSegmenter class from file AgroTool_ColorSegmenter.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    return SDUAgroTools(iface)
