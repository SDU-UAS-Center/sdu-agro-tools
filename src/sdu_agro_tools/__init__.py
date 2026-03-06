import toml
from qgis.gui import QgisInterface

from .sdu_agro_tools import SDUAgroTools

# Current version
version = None
with open("../../src/sdu_agro_tools/metadata.txt") as f:
    for line in f.readlines():
        if line.startswith("version="):
            version = line.split("=")[-1]
            break


def classFactory(iface: QgisInterface) -> SDUAgroTools:
    """Load AgroTool_ColorSegmenter class from file AgroTool_ColorSegmenter.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    return SDUAgroTools(iface)
