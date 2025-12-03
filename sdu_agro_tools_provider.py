import inspect
import os

from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from .cdc_algorithm import CDCAlgorithm


class SDUAgroToolsProvider(QgsProcessingProvider):  # type: ignore[misc]
    def __init__(self) -> None:
        """
        Default constructor.
        """
        QgsProcessingProvider.__init__(self)

    def unload(self) -> None:
        """
        Unloads the provider. Any tear-down steps required by the provider
        should be implemented here.
        """
        pass

    def loadAlgorithms(self) -> None:
        """
        Loads all algorithms belonging to this provider.
        """
        self.addAlgorithm(CDCAlgorithm())
        # add additional algorithms here
        # self.addAlgorithm(MyOtherAlgorithm())

    def id(self) -> str:
        """
        Returns the unique provider id, used for identifying the provider. This
        string should be a unique, short, character only string, eg "qgis" or
        "gdal". This string should not be localised.
        """
        return "SDU"

    def name(self) -> str:
        """
        Returns the provider name, which is used to describe the provider
        within the GUI.

        This string should be short (e.g. "Lastools") and localised.
        """
        return self.tr("SDU")  # type: ignore[no-any-return]

    def icon(self) -> QIcon:
        """
        Should return a QIcon which is used for your provider inside
        the Processing toolbox.
        """
        cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]  # type: ignore[arg-type]
        icon = QIcon(os.path.join(os.path.join(cmd_folder, "icon.png")))
        return icon

    def longName(self) -> str:
        """
        Returns the a longer version of the provider name, which can include
        extra details such as version numbers. E.g. "Lastools LIDAR tools
        (version 2.2.1)". This string should be localised. The default
        implementation returns the same string as name().
        """
        return self.name()
