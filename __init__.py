def classFactory(iface):  # pylint: disable=invalid-name
    """Load AgroTool_ColorSegmenter class from file AgroTool_ColorSegmenter.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .sdu_agro_tools import SDUAgroTools

    return SDUAgroTools(iface)
