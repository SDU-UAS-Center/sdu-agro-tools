import os
from pathlib import Path
from typing import Any

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsMapLayerProxyModel,
    QgsMessageLog,
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

from ..utils.task_progress_bar import TaskProgressBarDialog
from .crop_row_toolbar_dialog_ui import Ui_CropRowToolbarDialog


class CropRowToolbarDialog(QtWidgets.QDialog, Ui_CropRowToolbarDialog):  # type: ignore[misc]
    def __init__(
        self,
        alg: QgsProcessingAlgorithm,
        parent: QtWidgets.QWidget | None = None,
        context: QgsProcessingContext | None = None,
        feedback: QgsProcessingFeedback | None = None,
    ) -> None:
        super().__init__(parent)
        self.setupUi(self)
        self.alg = alg
        self.context = context
        self.feedback = feedback
        self.set_initial_param()
        self.connect_signals()
        icon_path = str(Path(__file__).parent / "sdu_logo_hs.jpg")
        self.logo.setPixmap(QPixmap(icon_path))

    def set_initial_param(self) -> None:
        self.input_file_cdc_map_layer_combo_box.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.input_file_ortho_map_layer_combo_box.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.input_file_ortho_map_layer_combo_box.setAllowEmptyLayer(True, text="Use Color Distance Image")

    def connect_signals(self) -> None:
        self.input_file_cdc_button.clicked.connect(self.load_input_color_distance_image)
        self.input_file_ortho_button.clicked.connect(self.load_input_ortho)
        self.output_ortho_button.clicked.connect(self.choose_save_ortho)
        self.output_crop_points_button.clicked.connect(self.choose_save_crop_points)
        self.output_crop_row_button.clicked.connect(self.choose_save_crop_row)
        self.output_crop_folder_button.clicked.connect(self.choose_save_folder)
        self.dialog_button_box.accepted.connect(self.on_accepted)
        self.dialog_button_box.rejected.connect(self.on_rejected)
        self.dialog_button_box.helpRequested.connect(self.on_help)

    def load_input_color_distance_image(self) -> None:
        raster_filename, _ = QFileDialog.getOpenFileName(self, "Select Raster File", "", "*.tif *.tiff")
        if raster_filename:
            layer_name = os.path.splitext(os.path.basename(raster_filename))[0]
            raster_layer = QgsRasterLayer(raster_filename, layer_name)
            if not raster_layer.isValid():
                QMessageBox.warning(self, "Invalid Layer", "The selected layer is not valid.")
                return
            QgsProject.instance().addMapLayer(raster_layer)
            self.input_file_cdc_map_layer_combo_box.setLayer(raster_layer)

    def load_input_ortho(self) -> None:
        raster_filename, _ = QFileDialog.getOpenFileName(self, "Select Raster File", "", "*.tif *.tiff")
        if raster_filename:
            layer_name = os.path.splitext(os.path.basename(raster_filename))[0]
            raster_layer = QgsRasterLayer(raster_filename, layer_name)
            if not raster_layer.isValid():
                QMessageBox.warning(self, "Invalid Layer", "The selected layer is not valid.")
                return
            QgsProject.instance().addMapLayer(raster_layer)
            self.input_file_ortho_map_layer_combo_box.setLayer(raster_layer)

    def choose_save_ortho(self) -> None:
        output_file, _ = QFileDialog.getSaveFileName(self, "Select Output File", "", "*.tif")
        if output_file:
            if not output_file.endswith(".tif"):
                output_file += ".tif"
            self.output_ortho_line_edit.setText(output_file)

    def choose_save_crop_points(self) -> None:
        output_file, _ = QFileDialog.getSaveFileName(self, "Select Output File", "", "*.gpkg")
        if output_file:
            if not output_file.endswith(".gpkg"):
                output_file += ".gpkg"
            self.output_crop_points_line_edit.setText(output_file)

    def choose_save_crop_row(self) -> None:
        output_file, _ = QFileDialog.getSaveFileName(self, "Select Output File", "", "*.gpkg")
        if output_file:
            if not output_file.endswith(".gpkg"):
                output_file += ".gpkg"
            self.output_crop_row_line_edit.setText(output_file)

    def choose_save_folder(self) -> None:
        output_folder = QFileDialog.getExistingDirectory(self, "Select Output Folder", "")
        if self.output_exists(output_folder):
            QMessageBox.warning(
                self,
                "Output folder already contains crop information.",
                "Output folder already contains crop information. \nCrop information will be overwritten.",
            )
        if output_folder:
            self.output_crop_folder_line_edit.setText(output_folder)

    def output_exists(self, output_folder: str) -> bool:
        output_path = Path(output_folder)
        points_path = output_path.joinpath("points_in_rows.csv")
        row_path = output_path.joinpath("row_information.csv")
        global_row_path = output_path.joinpath("row_information_global.csv")
        return bool(points_path.exists() or row_path.exists() or global_row_path.exists())

    def on_accepted(self) -> None:
        params = {}
        params.update({"INPUT": self.input_file_cdc_map_layer_combo_box.currentLayer()})
        if "INPUT" not in params:
            QMessageBox.warning(self, "Missing input raster", "Please load a valid input raster layer.")
            return
        if self.input_file_ortho_map_layer_combo_box.currentLayer() is not None:
            params.update({"ORTHO": self.input_file_ortho_map_layer_combo_box.currentLayer()})
        if self.output_ortho_line_edit.text():
            params.update({"OUTPUT_ORTHO": self.output_ortho_line_edit.text()})
        else:
            params.update({"OUTPUT_ORTHO": "TEMPORARY_OUTPUT"})
        if self.output_crop_points_line_edit.text():
            params.update({"OUTPUT_POINTS": self.output_crop_points_line_edit.text()})
        else:
            params.update({"OUTPUT_POINTS": "TEMPORARY_OUTPUT"})
        if self.output_crop_row_line_edit.text():
            params.update({"OUTPUT_ROWS": self.output_crop_row_line_edit.text()})
        else:
            params.update({"OUTPUT_ROWS": "TEMPORARY_OUTPUT"})
        if self.output_crop_folder_line_edit.text():
            params.update({"OUTPUT_FOLDER": self.output_crop_folder_line_edit.text()})
        else:
            QMessageBox.warning(
                self, "Missing output folder", "Please select a folder to save crop row information to."
            )
            return
        params.update({"SAVE_ORTHO": self.output_ortho_checkbox.isChecked()})
        params.update({"SAVE_CROP_POINTS": self.output_crop_points_checkbox.isChecked()})
        params.update({"SAVE_CROP_ROWS": self.output_crop_rows_checkbox.isChecked()})
        params.update({"THRESHOLD": self.threshold_spin_box.value()})
        params.update({"VEG_THRESHOLD": self.veg_threshold_spin_box.value()})
        params.update({"CROP_ROW_DISTANCE": self.crop_row_distance_spinbox.value()})
        params.update({"MIN_ANGLE": self.min_angle_spin_box.value()})
        params.update({"MAX_ANGLE": self.max_angle_spin_box.value()})
        params.update({"ANGLE_RESOLUTION": self.angle_resolution_spin_box.value()})
        params.update({"TILE_WIDTH": self.tile_width_spin_box.value()})
        params.update({"TILE_HEIGHT": self.tile_hight_spin_box.value()})
        params.update({"TILE_OVERLAP": self.tile_overlap_spin_box.value()})
        params.update({"TILE_BOUNDARY": self.tile_boundary_checkbox.isChecked()})
        params.update({"USE_PROCESS_POOL": self.use_processing_pools_checkbox.isChecked()})
        self.accept()
        QgsMessageLog.logMessage(
            f"Calling crop-row-detector task with parameters: {params}",
            tag="SDU Agro Tools",
            level=Qgis.MessageLevel.Info,
        )
        task = CropRowToolbarTask(alg=self.alg, params=params, context=self.context, feedback=self.feedback)
        QgsApplication.instance().taskManager().addTask(task)

    def on_rejected(self) -> None:
        self.reject()

    def on_help(self) -> None:
        QDesktopServices.openUrl(
            QUrl("https://sdu-uas-center.github.io/sdu-agro-tools/")
        )  # todo change to documentation


class CropRowToolbarTask(QgsTask):  # type: ignore[misc]
    def __init__(
        self,
        alg: QgsProcessingAlgorithm,
        params: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> None:
        super().__init__("CropRowToolbarTask", QgsTask.CanCancel)
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
        self.progressDlg.setWindowTitle("SDU Agro Tools Crop Row Processing")
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
        if results["OUTPUT_ORTHO"] is not None:
            if results["OUTPUT_ORTHO"].startswith("/tmp"):
                name = "Output orthomosaic with crop rows"
            else:
                name = os.path.splitext(os.path.basename(results["OUTPUT_ORTHO"]))[0]
            output = QgsRasterLayer(results["OUTPUT_ORTHO"], name)
            QgsProject.instance().addMapLayer(output)
        if results["OUTPUT_POINTS"] is not None:
            if results["OUTPUT_POINTS"].startswith("/tmp"):
                name = "Output crop points"
            else:
                name = os.path.splitext(os.path.basename(results["OUTPUT_POINTS"]))[0]
            output = QgsVectorLayer(results["OUTPUT_POINTS"], name)
            QgsProject.instance().addMapLayer(output)
        if results["OUTPUT_ROWS"] is not None:
            if results["OUTPUT_ROWS"].startswith("/tmp"):
                name = "Output crop rows"
            else:
                name = os.path.splitext(os.path.basename(results["OUTPUT_ROWS"]))[0]
            output = QgsVectorLayer(results["OUTPUT_ROWS"], name)
            QgsProject.instance().addMapLayer(output)
        return True

    def finished(self, result: bool) -> Any:
        self.alg.postProcess(self.context, self.feedback)
        self.progressDlg.close()
        return super().finished(result)
