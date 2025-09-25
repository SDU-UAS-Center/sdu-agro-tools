def classFactory(iface):  # pylint: disable=invalid-name
    """Load AgroTool_ColorSegmenter class from file AgroTool_ColorSegmenter.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .AgroTool_ColorSegmenter import AgroTool_ColorSegmenter
    return AgroTool_ColorSegmenter(iface)
