import inspect
import os.path
import sys
from collections.abc import Callable
from typing import Any

from qgis.core import QgsApplication
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QCoreApplication, QSettings, QTranslator
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QWidget

from .cdc_algorithm import CDCAlgorithm
from .cdc_toolbar_dialog import CDCToolbarDialog

# Initialize Qt resources from file resources.py
# from .resources import *
from .sdu_agro_tools_provider import SDUAgroToolsProvider

cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]  # type: ignore[arg-type]

if cmd_folder not in sys.path:
    sys.path.insert(0, cmd_folder)


class SDUAgroTools:
    """QGIS Plugin Implementation."""

    def __init__(self, iface: QgisInterface) -> None:
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value("locale/userLocale")[0:2]
        locale_path = os.path.join(self.plugin_dir, "i18n", f"AgroTool_ColorSegmenter_{locale}.qm")

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions: list[Any] = []
        self.menu: str = self.tr("&AgroTool Color Segmenter")

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start: bool | None = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message: str) -> str:
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate("AgroTool_ColorSegmenter", message)  # type: ignore[no-any-return]

    def add_action(
        self,
        icon_path: str,
        text: str,
        callback: Callable[[], None],
        enabled_flag: bool = True,
        add_to_menu: bool = True,
        add_to_toolbar: bool = True,
        status_tip: str | None = None,
        whats_this: str | None = None,
        parent: QWidget | None = None,
    ) -> Any:
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)

        return action

    def initGui(self) -> None:
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = os.path.join(os.path.join(cmd_folder, "icon.png"))
        self.add_action(
            icon_path,
            text=self.tr("SDU Agro Tools CDC"),
            callback=self.run_cdc,
            parent=self.iface.mainWindow(),
        )

        # will be set False in run()
        self.first_start = True

        # Init provider:
        self.provider = SDUAgroToolsProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def unload(self) -> None:
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(self.tr("&AgroTool Color Segmenter"), action)
            self.iface.removeToolBarIcon(action)

        # Remove provider:
        QgsApplication.processingRegistry().removeProvider(self.provider)
        # gives error on closing qgis

    def run_cdc(self) -> None:
        """Run method that performs all the real work"""
        alg = CDCAlgorithm()
        alg_dialog = CDCToolbarDialog(alg)
        alg_dialog.exec()
