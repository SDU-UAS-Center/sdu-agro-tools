import inspect
import os
from typing import Any

from qgis.core import (
    QgsApplication,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProject,
    QgsRasterLayer,
    QgsTask,
    QgsVectorLayer,
)
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices, QPixmap
from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox

from .cdc_toolbar_dialog_ui import Ui_CDCToolbarDialog
from .task_progress_bar import TaskProgressBarDialog


class CDCToolbarDialog(QtWidgets.QDialog, Ui_CDCToolbarDialog):  # type: ignore[misc]
    def __init__(
        self,
        alg: QgsProcessingAlgorithm,
        parent: QtWidgets.QWidget | None = None,
        context: QgsProcessingContext | None = None,
        feedback: QgsProcessingFeedback | None = None,
    ) -> None:
        super().__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.alg = alg
        self.context = context
        self.feedback = feedback
        self.set_initial_param()
        self.connect_signals()
        cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]  # type: ignore[arg-type]
        icon_path = os.path.join(os.path.join(cmd_folder, "sdu_logo_hs.jpg"))
        self.logo.setPixmap(QPixmap(icon_path))

    def get_all_layers_filtered_by_type(self, layer_type: Any) -> list[Any]:
        return [layer for layer in QgsProject.instance().mapLayers().values() if isinstance(layer, layer_type)]

    def set_initial_param(self) -> None:
        self.input_file_combobox.addItems(
            [layer.name() for layer in self.get_all_layers_filtered_by_type(QgsRasterLayer)]
        )
        self.set_bands_to_use()
        self.shape_file_combobox.addItems(
            [layer.name() for layer in self.get_all_layers_filtered_by_type(QgsVectorLayer)]
        )
        self.ref_image_combobox.addItems(
            [layer.name() for layer in self.get_all_layers_filtered_by_type(QgsRasterLayer)]
        )
        self.pixel_mask_combobox.addItems(
            [layer.name() for layer in self.get_all_layers_filtered_by_type(QgsRasterLayer)]
        )
        self.metric_combo_box.addItems(["Mahalanobis", "GMM"])

    def connect_signals(self) -> None:
        self.input_file_combobox.currentIndexChanged.connect(self.set_bands_to_use)
        self.input_file_button.clicked.connect(self.load_input_raster)
        self.shape_file_button.clicked.connect(self.load_shape_file)
        self.ref_image_button.clicked.connect(self.load_ref_image)
        self.pixel_mask_button.clicked.connect(self.load_pixel_mask)
        self.metric_combo_box.currentIndexChanged.connect(self.select_metric)
        self.tile_processing_checkbox.stateChanged.connect(self.select_tile_processing)
        self.output_file_button.clicked.connect(self.choose_save_file)
        self.dialog_button_box.accepted.connect(self.on_accepted)
        self.dialog_button_box.rejected.connect(self.on_rejected)
        self.dialog_button_box.helpRequested.connect(self.on_help)

    def set_bands_to_use(self) -> None:
        selected_raster_name = self.input_file_combobox.currentText()
        for layer in self.get_all_layers_filtered_by_type(QgsRasterLayer):
            if layer.name() == selected_raster_name:
                band_list = []
                for band in range(1, layer.bandCount() + 1):
                    band_name = layer.bandName(band)
                    band_list.append(f"{band}: {band_name}")
                self.bands_to_use_combo_box.clear()
                self.bands_to_use_combo_box.addItems(band_list)
                self.bands_to_use_combo_box.setEnabled(True)
                self.bands_to_use_combo_box.selectAllOptions()
                self.bands_to_use_combo_box.toggleItemCheckState(len(band_list) - 1)
                return

    def load_input_raster(self) -> None:
        raster_filename, _ = QFileDialog.getOpenFileName(self, "Select Raster File", "", "*.tif")
        if raster_filename:
            layer_name = os.path.splitext(os.path.basename(raster_filename))[0]
            raster_layer = QgsRasterLayer(raster_filename, layer_name)
            if not raster_layer.isValid():
                QMessageBox.warning(self, "Invalid Layer", "The selected layer is not valid.")
                return
            QgsProject.instance().addMapLayer(raster_layer)
            self.input_file_combobox.addItem(raster_layer.name())
            self.input_file_combobox.setCurrentText(raster_layer.name())

    def load_shape_file(self) -> None:
        shape_filename, _ = QFileDialog.getOpenFileName(self, "Select Shape File", "", "*.shp")
        if shape_filename:
            layer_name = os.path.splitext(os.path.basename(shape_filename))[0]
            vector_layer = QgsVectorLayer(shape_filename, layer_name, "ogr")
            if not vector_layer.isValid():
                QMessageBox.warning(self, "Invalid Layer", "The selected shapefile is not valid.")
                return
            QgsProject.instance().addMapLayer(vector_layer)
            self.shape_file_combobox.addItem(vector_layer.name())
            self.shape_file_combobox.setCurrentText(vector_layer.name())

    def load_ref_image(self) -> None:
        ref_image_filename, _ = QFileDialog.getOpenFileName(self, "Select Reference Image", "", "*.tif *.jpg *jpeg")
        if ref_image_filename:
            layer_name = os.path.splitext(os.path.basename(ref_image_filename))[0]
            ref_image = QgsRasterLayer(ref_image_filename, layer_name)
            if not ref_image.isValid():
                QMessageBox.warning(self, "Invalid Layer", "The selected layer is not valid.")
                return
            QgsProject.instance().addMapLayer(ref_image)
            self.ref_image_combobox.addItem(ref_image.name())
            self.ref_image_combobox.setCurrentText(ref_image.name())

    def load_pixel_mask(self) -> None:
        pixel_mask_filename, _ = QFileDialog.getOpenFileName(self, "Select Pixel Mask", "", "*.tif *.jpg *jpeg")
        if pixel_mask_filename:
            layer_name = os.path.splitext(os.path.basename(pixel_mask_filename))[0]
            pixel_mask = QgsRasterLayer(pixel_mask_filename, layer_name)
            if not pixel_mask.isValid():
                QMessageBox.warning(self, "Invalid Layer", "The selected layer is not valid.")
                return
            QgsProject.instance().addMapLayer(pixel_mask)
            self.pixel_mask_combobox.addItem(pixel_mask.name())
            self.pixel_mask_combobox.setCurrentText(pixel_mask.name())

    def select_metric(self) -> None:
        if self.metric_combo_box.currentText() == "GMM":
            self.gmm_components_spin_box.setEnabled(True)
            self.gmm_components_label.setEnabled(True)
        else:
            self.gmm_components_spin_box.setEnabled(False)
            self.gmm_components_label.setEnabled(False)

    def select_tile_processing(self) -> None:
        checked = self.tile_processing_checkbox.isChecked()
        self.tile_description.setEnabled(checked)
        self.tile_hight_label.setEnabled(checked)
        self.tile_hight_spin_box.setEnabled(checked)
        self.tile_width_label.setEnabled(checked)
        self.tile_width_spin_box.setEnabled(checked)
        self.tile_overlap_label.setEnabled(checked)
        self.tile_overlap_spin_box.setEnabled(checked)

    def choose_save_file(self) -> None:
        output_file, _ = QFileDialog.getSaveFileName(self, "Select Output File", "", "*.tif")
        if output_file:
            self.output_line_edit.setText(output_file)

    def on_accepted(self) -> None:
        self.accept()
        params = {}
        for layer in self.get_all_layers_filtered_by_type((QgsRasterLayer, QgsVectorLayer)):
            if layer.name() == self.input_file_combobox.currentText():
                params.update({"INPUT": layer})
            if layer.name() == self.shape_file_combobox.currentText():
                params.update({"SHAPE_FILE": layer})
            if layer.name() == self.ref_image_combobox.currentText():
                params.update({"REFERENCE": layer})
            if layer.name() == self.pixel_mask_combobox.currentText():
                params.update({"ANNOTATED": layer})
        if "INPUT" not in params:
            QMessageBox.warning(self, "Missing input raster", "Please load a valid input raster layer.")
        bands_to_use = [int(b.split(":")[0]) for b in self.bands_to_use_combo_box.checkedItems()]
        if not bands_to_use:
            QMessageBox.warning(self, "No Bands selected", "Please select a which bands to use.")
        params.update({"BANDS": bands_to_use})
        params.update({"REF_TYPE": self.color_ref_tab_widget.currentIndex()})
        if params["REF_TYPE"] == 0:
            if "SHAPE_FILE" not in params:
                QMessageBox.warning(self, "Missing shape file", "Please select a valid shape file.")
        else:
            if "REFERENCE" not in params:
                QMessageBox.warning(
                    self,
                    "Missing reference image",
                    "Please seletc a valid reference image.",
                )
            if "ANNOTATED" not in params:
                QMessageBox.warning(self, "Missing pixel mask", "Please select a valid pixel mask.")
        if self.output_line_edit.text():
            params.update({"OUTPUT": self.output_line_edit.text()})
        else:
            params.update({"OUTPUT": "TEMPORARY_OUTPUT"})
        params.update({"COLOR_MODEL": self.metric_combo_box.currentText()})
        params.update({"GMM_PARAM": self.gmm_components_spin_box.value()})
        params.update({"TILE_PROCESSING": self.tile_processing_checkbox.isChecked()})
        params.update({"TILE_WIDTH": self.tile_width_spin_box.value()})
        params.update({"TILE_HEIGHT": self.tile_hight_spin_box.value()})
        params.update({"TILE_OVERLAP": self.tile_overlap_spin_box.value() / 100})
        params.update({"CONVERT_UINT8": self.output_uint_checkbox.isChecked()})
        params.update({"SCALE": self.output_scale_spinbox.value()})
        task = CDCToolbarTask(alg=self.alg, params=params, context=self.context, feedback=self.feedback)
        QgsApplication.instance().taskManager().addTask(task)

    def on_rejected(self) -> None:
        self.reject()

    def on_help(self) -> None:
        QDesktopServices.openUrl(QUrl("https://google.com"))


class CDCToolbarTask(QgsTask):  # type: ignore[misc]
    """
    Auxiliary class - wraps the algorithm in a QTask object which allows concurrent execution
    and does not block the main QGIS thread.

    Add OUTPUT to current QGIS project - need to do manually this with custom GUI

    When you have a custom GUI, the execution of the algorithm must be done with this class:

    task = MyProcessingTask(alg = self.alg, params = params)
    self.active_task.append(task) -> Need to keep a reference to the task
    QgsApplication.instance().taskManager().addTask(task)

    """

    def __init__(
        self,
        alg: QgsProcessingAlgorithm,
        params: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> None:
        super().__init__("CDCToolbarTask", QgsTask.CanCancel)
        self.alg = alg
        self.params = params
        if context is None:
            self.context = QgsProcessingContext()
            self.context.setProject(QgsProject.instance())
        else:
            self.context = context
        if feedback is None:
            self.feedback = QgsProcessingFeedback()
        else:
            self.feedback = feedback
        self.progressDlg = TaskProgressBarDialog()
        self.progressDlg.setWindowTitle("SDU Agro Tools CDC Processing")
        self.progressDlg.show()

        self.feedback.progressChanged.connect(lambda progress: self.progressDlg.progressBar.setValue(int(progress)))
        self.progressDlg.signal.cancel_signal.connect(self.feedback.cancel)
        self.progressDlg.signal.cancel_signal.connect(self.cancel)
        self.alg.initAlgorithm(None)
        self.alg.prepare(params, self.context, self.feedback)

    def run(self) -> bool:
        results = self.alg.runPrepared(self.params, self.context, self.feedback)
        if self.feedback.isCanceled():
            return False
        if results["OUTPUT"].startswith("/tmp"):
            name = "Output"
        else:
            name = os.path.splitext(os.path.basename(self._results["OUTPUT"]))[0]
        output = QgsRasterLayer(results["OUTPUT"], name)
        QgsProject.instance().addMapLayer(output)
        return True

    def finished(self, result: bool) -> Any:
        self.alg.postProcess(self.context, self.feedback)
        self.progressDlg.close()
        return super().finished(result)
