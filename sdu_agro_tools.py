import os.path
from pathlib import Path

from qgis.core import QgsApplication
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QCoreApplication, QSettings, Qt, QTranslator, QUrl
from qgis.PyQt.QtGui import QDesktopServices, QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu, QToolButton

from .cdc_algorithm import CDCAlgorithm
from .cdc_toolbar_dialog import CDCToolbarDialog
from .crop_row_algorithm import CropRowAlgorithm
from .sdu_agro_tools_provider import SDUAgroToolsProvider


class SDUAgroTools:
    def __init__(self, iface: QgisInterface) -> None:
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        locale = QSettings().value("locale/userLocale")[0:2]
        locale_path = os.path.join(self.plugin_dir, "i18n", f"SDU_Agro_Tools_{locale}.qm")
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)
        self.menu: QMenu | None = None

    def tr(self, message: str) -> str:
        return QCoreApplication.translate("SDU_Agro_Tools", message)  # type: ignore[no-any-return]

    def initGui(self) -> None:
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon = QIcon(str(Path(__file__).parent / "icon.png"))
        self.menu = self.iface.pluginMenu().addMenu(icon, self.tr("&SDU Agro Tools"))
        self.toolButton = QToolButton()
        self.toolButton.setMenu(QMenu())
        self.toolButton.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.toolButton.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toolButtonMenu = self.toolButton.menu()
        cdc_action = QAction(icon, self.tr("Calculate Color Distance"), self.iface.mainWindow())
        cdc_action.triggered.connect(self.run_cdc)
        toolButtonMenu.addAction(cdc_action)
        self.toolButton.setDefaultAction(cdc_action)
        self.toolButton.setText(cdc_action.text())
        self.menu.addAction(cdc_action)
        crop_row_action = QAction(icon, self.tr("Detect Crop Rows"), self.iface.mainWindow())
        crop_row_action.triggered.connect(self.run_crop_row)
        toolButtonMenu.addAction(crop_row_action)
        self.menu.addAction(crop_row_action)
        toolButtonMenu.addSeparator()
        self.menu.addSeparator()
        help_action = QAction(
            QIcon(":images/themes/default/mActionHelpContents.svg"), self.tr("Documentation"), self.iface.mainWindow()
        )
        help_action.triggered.connect(self.open_help)
        toolButtonMenu.addAction(help_action)
        self.menu.addAction(help_action)
        self.iface.addToolBarWidget(self.toolButton)
        self.provider = SDUAgroToolsProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def unload(self) -> None:
        """Removes the plugin menu item and icon from QGIS GUI."""
        if not self.menu:
            return
        self.iface.pluginMenu().removeAction(self.menu.menuAction())
        self.toolButton.deleteLater()
        QgsApplication.processingRegistry().removeProvider(self.provider)

    def open_help(self) -> None:
        QDesktopServices.openUrl(QUrl("https://google.com"))  # todo add link to docs

    def run_cdc(self) -> None:
        """Run method that performs all the real work"""
        alg = CDCAlgorithm()
        alg_dialog = CDCToolbarDialog(alg)
        alg_dialog.exec()

    def run_crop_row(self) -> None:
        """Run method that performs all the real work"""
        alg = CropRowAlgorithm()
        alg_dialog = CDCToolbarDialog(alg)
        alg_dialog.exec()
