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
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices, QPixmap
from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox

from ..utils.task_progress_bar import TaskProgressBarDialog

DIALOG_CLASS = uic.loadUiType(os.path.join(os.path.dirname(__file__), "crop_row_connector_toolbar_dialog.ui"))[0]


class CropRowConnectorToolbarDialog(QtWidgets.QDialog, DIALOG_CLASS):  # type: ignore[misc, valid-type]
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
        icon_path = str(Path(__file__).parent.parent / "sdu_logo_hs.jpg")
        self.logo.setPixmap(QPixmap(icon_path))

    def set_initial_param(self) -> None:
        self.input_file_points_map_layer_combo_box.setFilters(QgsMapLayerProxyModel.Filter.VectorLayer)
        self.input_file_rows_map_layer_combo_box.setFilters(QgsMapLayerProxyModel.Filter.VectorLayer)

    def connect_signals(self) -> None:
        self.input_file_points_button.clicked.connect(self.load_input_points)
        self.input_file_rows_button.clicked.connect(self.load_input_rows)
        self.output_healthy_rows_button.clicked.connect(self.choose_save_healthy)
        self.output_unhealthy_rows_button.clicked.connect(self.choose_save_unhealthy)
        self.dialog_button_box.accepted.connect(self.on_accepted)
        self.dialog_button_box.rejected.connect(self.on_rejected)
        self.dialog_button_box.helpRequested.connect(self.on_help)

    def load_input_points(self) -> None:
        vector_filename, _ = QFileDialog.getOpenFileName(self, "Select Vector File", "", "*.gpkg")
        if vector_filename:
            layer_name = os.path.splitext(os.path.basename(vector_filename))[0]
            vector_layer = QgsVectorLayer(vector_filename, layer_name)
            if not vector_layer.isValid():
                QMessageBox.warning(self, "Invalid Layer", "The selected layer is not valid.")
                return
            QgsProject.instance().addMapLayer(vector_layer)
            self.input_file_points_map_layer_combo_box.setLayer(vector_layer)

    def load_input_rows(self) -> None:
        vector_filename, _ = QFileDialog.getOpenFileName(self, "Select Vector File", "", "*.gpkg")
        if vector_filename:
            layer_name = os.path.splitext(os.path.basename(vector_filename))[0]
            vector_layer = QgsRasterLayer(vector_filename, layer_name)
            if not vector_layer.isValid():
                QMessageBox.warning(self, "Invalid Layer", "The selected layer is not valid.")
                return
            QgsProject.instance().addMapLayer(vector_layer)
            self.input_file_rows_map_layer_combo_box.setLayer(vector_layer)

    def choose_save_healthy(self) -> None:
        output_file, _ = QFileDialog.getSaveFileName(self, "Select Output File", "", "*.gpkg")
        if output_file:
            if not output_file.endswith(".gpkg"):
                output_file += ".gpkg"
            self.output_healthy_rows_line_edit.setText(output_file)

    def choose_save_unhealthy(self) -> None:
        output_file, _ = QFileDialog.getSaveFileName(self, "Select Output File", "", "*.gpkg")
        if output_file:
            if not output_file.endswith(".gpkg"):
                output_file += ".gpkg"
            self.output_unhealthy_rows_line_edit.setText(output_file)

    def on_accepted(self) -> None:
        params = {}
        params.update({"INPUT_ROWS": self.input_file_rows_map_layer_combo_box.currentLayer()})
        if "INPUT_ROWS" not in params:
            QMessageBox.warning(self, "Missing input rows", "Please load a valid input vector layer.")
            return
        params.update({"INPUT_POINTS": self.input_file_points_map_layer_combo_box.currentLayer()})
        if "INPUT_POINTS" not in params:
            QMessageBox.warning(self, "Missing input points", "Please load a valid input vector layer.")
            return
        if self.output_healthy_rows_line_edit.text():
            params.update({"OUTPUT_HEALTHY": self.output_healthy_rows_line_edit.text()})
        else:
            params.update({"OUTPUT_HEALTHY": "TEMPORARY_OUTPUT"})
        if self.output_unhealthy_rows_line_edit.text():
            params.update({"OUTPUT_UNHEALTHY": self.output_unhealthy_rows_line_edit.text()})
        else:
            params.update({"OUTPUT_UNHEALTHY": "TEMPORARY_OUTPUT"})
        params.update({"ANGLE_TOLERANCE": self.angle_spin_box.value()})
        params.update({"DISTANCE_TOLERANCE": self.distance_spin_box.value() / 100})
        params.update({"VEGETATION_THRESHOLD": self.vegetation_spin_box.value()})
        params.update({"MIN_UNHEALTHY_VEGETATION_LENGTH": self.min_unhealthy_segment_length_spin_box.value() / 100})
        params.update({"MAX_SEGMENT_LENGTH": self.max_segment_length_spin_box.value()})
        self.accept()
        QgsMessageLog.logMessage(
            f"Calling crop-row-connector task with parameters: {params}",
            tag="SDU Agro Tools",
            level=Qgis.MessageLevel.Info,
        )
        task = CropRowConnectorToolbarTask(alg=self.alg, params=params, context=self.context, feedback=self.feedback)
        QgsApplication.instance().taskManager().addTask(task)

    def on_rejected(self) -> None:
        self.reject()

    def on_help(self) -> None:
        QDesktopServices.openUrl(
            QUrl("https://sdu-uas-center.github.io/sdu-agro-tools/")
        )  # todo change to documentation


class CropRowConnectorToolbarTask(QgsTask):  # type: ignore[misc]
    def __init__(
        self,
        alg: QgsProcessingAlgorithm,
        params: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> None:
        super().__init__("CropRowToolbarTask", QgsTask.Flag.CanCancel)
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
        self.progressDlg.setWindowTitle("SDU Agro Tools Crop Row Connector Processing")
        self.progressDlg.progressBar.setMinimum(0)
        self.progressDlg.progressBar.setMaximum(0)
        self.progressDlg.show()
        self.progressDlg.signal.cancel_signal.connect(self.feedback.cancel)
        self.progressDlg.signal.cancel_signal.connect(self.cancel)
        self.alg.initAlgorithm(None)
        self.alg.prepare(params, self.context, self.feedback)

    def run(self) -> bool:
        results = self.alg.runPrepared(self.params, self.context, self.feedback)
        if self.feedback.isCanceled():
            return False
        if results["OUTPUT_HEALTHY"] is not None:
            if self.params["OUTPUT_HEALTHY"] == "TEMPORARY_OUTPUT":
                name = "Output healthy crop rows"
            else:
                name = os.path.splitext(os.path.basename(results["OUTPUT_HEALTHY"]))[0]
            output = QgsVectorLayer(results["OUTPUT_HEALTHY"], name)
            QgsProject.instance().addMapLayer(output)
        if results["OUTPUT_UNHEALTHY"] is not None:
            if self.params["OUTPUT_UNHEALTHY"] == "TEMPORARY_OUTPUT":
                name = "Output unhealthy crop rows"
            else:
                name = os.path.splitext(os.path.basename(results["OUTPUT_UNHEALTHY"]))[0]
            output = QgsVectorLayer(results["OUTPUT_UNHEALTHY"], name)
            QgsProject.instance().addMapLayer(output)
        return True

    def finished(self, result: bool) -> Any:
        self.alg.postProcess(self.context, self.feedback)
        self.progressDlg.close()
        return super().finished(result)
