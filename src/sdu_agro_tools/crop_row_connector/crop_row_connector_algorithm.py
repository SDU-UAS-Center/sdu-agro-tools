from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from crop_row_connector import CombineCropRows
from qgis.core import (
    Qgis,
    QgsFeature,
    QgsGeometry,
    QgsMessageLog,
    QgsPoint,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingParameterNumber,
    QgsProcessingParameterVectorDestination,
    QgsProcessingParameterVectorLayer,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QCoreApplication


class CropRowConnectorAlgorithm(QgsProcessingAlgorithm):  # type: ignore[misc]
    """
    This is an example algorithm that takes a vector layer and
    creates a new identical one.

    It is meant to be used as an example of how to create your own
    algorithms and explain methods and variables used to do it. An
    algorithm like this will be available in all elements, and there
    is not need for additional work.

    All Processing algorithms should extend the QgsProcessingAlgorithm
    class.
    """

    OUTPUT_HEALTHY = "OUTPUT_HEALTHY"
    OUTPUT_UNHEALTHY = "OUTPUT_UNHEALTHY"
    INPUT_ROWS = "INPUT_ROWS"
    INPUT_POINTS = "INPUT_POINTS"
    ANGLE_TOLERANCE = "ANGLE_TOLERANCE"
    DISTANCE_TOLERANCE = "DISTANCE_TOLERANCE"
    VEGETATION_THRESHOLD = "VEGETATION_THRESHOLD"
    MIN_UNHEALTHY_VEGETATION_LENGTH = "MIN_UNHEALTHY_VEGETATION_LENGTH"
    MAX_SEGMENT_LENGTH = "MAX_SEGMENT_LENGTH"

    def initAlgorithm(self, config: dict[str, Any]) -> None:
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        self.addParameter(QgsProcessingParameterVectorLayer(self.INPUT_ROWS, self.tr("Input tiled crop rows")))
        self.addParameter(QgsProcessingParameterVectorLayer(self.INPUT_POINTS, self.tr("Input crop vegetation points")))

        self.addParameter(
            QgsProcessingParameterNumber(
                self.ANGLE_TOLERANCE,
                self.tr("Tolerance of angle between connected crop rows in degrees"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=10,
                minValue=0,
                maxValue=90,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DISTANCE_TOLERANCE,
                self.tr("Tolerance of distance between connected crop rows in meters"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.1,
                minValue=0,
                maxValue=100,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.VEGETATION_THRESHOLD,
                self.tr("Vegetation threshold for a point to be considered healthy"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=127,
                minValue=0,
                maxValue=255,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MIN_UNHEALTHY_VEGETATION_LENGTH,
                self.tr("Minimum length for a segment to be considered unhealthy in meters"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.1,
                minValue=0,
                maxValue=100,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_SEGMENT_LENGTH,
                self.tr("Maximum length of segments in meters"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=5,
                minValue=0,
            )
        )

        self.addParameter(
            QgsProcessingParameterVectorDestination(self.OUTPUT_HEALTHY, self.tr("Output healthy crop rows segments"))
        )
        self.addParameter(
            QgsProcessingParameterVectorDestination(
                self.OUTPUT_UNHEALTHY, self.tr("Output unhealthy crop rows segments")
            )
        )

    def prepareAlgorithm(
        self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback
    ) -> Any:
        QgsMessageLog.logMessage(
            f"Crop-row-connector called with parameters: {parameters}",
            tag="SDU Agro Tools",
            level=Qgis.MessageLevel.Info,
        )
        self.input_rows = self.parameterAsVectorLayer(parameters, self.INPUT_ROWS, context)
        self.input_points = self.parameterAsVectorLayer(parameters, self.INPUT_POINTS, context)
        self.angle_tol = self.parameterAsDouble(parameters, self.ANGLE_TOLERANCE, context)
        self.distance_tol = self.parameterAsDouble(parameters, self.DISTANCE_TOLERANCE, context)
        self.vegetation_threshold = self.parameterAsDouble(parameters, self.VEGETATION_THRESHOLD, context)
        self.min_unhealthy_veg_length = self.parameterAsDouble(
            parameters, self.MIN_UNHEALTHY_VEGETATION_LENGTH, context
        )
        self.max_segment_length = self.parameterAsDouble(parameters, self.MAX_SEGMENT_LENGTH, context)
        return super().prepareAlgorithm(parameters, context, feedback)

    def processAlgorithm(
        self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback
    ) -> dict[str, Any]:
        ccr = CombineCropRows(
            self.angle_tol,
            self.vegetation_threshold,
            self.min_unhealthy_veg_length,
            self.max_segment_length,
            self.distance_tol,
            max_workers=context.maximumThreads(),
        )
        row_features = self.input_rows.getFeatures()
        rows = pd.DataFrame([row_f.attributeMap() for row_f in row_features])
        rows = rows[
            [
                "tile",
                "x_position",
                "y_position",
                "angle",
                "row",
                "x_start",
                "y_start",
                "x_end",
                "y_end",
                "x_mid",
                "y_mid",
            ]
        ]
        row_information = rows.to_numpy(dtype=np.float64)
        tiles = ccr.separate_row_information_to_tile(row_information)
        grid = ccr.create_tile_grid(row_information, tiles)
        ccr.connect_rows_in_tiles(grid, tiles)
        ccr.ccrc.sort_connected_crop_rows()
        ccr.ccrc.check_dublicates()
        point_features = self.input_points.getFeatures()
        points = pd.DataFrame([point_f.attributeMap() for point_f in point_features])
        DF_vegetation_rows = points[["tile", "row", "x", "y", "vegetation"]]
        DF_crop_rows_new = ccr.merge_all_points_in_all_crop_rows_remove(
            ccr.ccrc.connected_crop_rows, DF_vegetation_rows, row_information, tiles
        )
        segments = ccr.separate_healthy_and_unhealthy_vegetation_segments(DF_crop_rows_new)
        crs = self.input_rows.sourceCrs().toWkt()
        healthy_layer, unhealthy_layer = self.create_vector_layers(segments, crs)

        output_healthy = self.parameterAsOutputLayer(parameters, self.OUTPUT_HEALTHY, context)
        output_unhealthy = self.parameterAsOutputLayer(parameters, self.OUTPUT_UNHEALTHY, context)
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.layerName = "Healthy crop rows"
        QgsVectorFileWriter.writeAsVectorFormatV3(
            healthy_layer, output_healthy, QgsProject.instance().transformContext(), options=options
        )
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.layerName = "Unhealthy crop rows"
        QgsVectorFileWriter.writeAsVectorFormatV3(
            unhealthy_layer, output_unhealthy, QgsProject.instance().transformContext(), options=options
        )
        return {self.OUTPUT_HEALTHY: output_healthy, self.OUTPUT_UNHEALTHY: output_unhealthy}

    def create_vector_layers(self, segments: list[dict[str, Any]], crs: str) -> tuple[QgsVectorLayer, QgsVectorLayer]:
        uri = f"LineString?crs={crs}"
        healthy_layer = QgsVectorLayer(uri, "temporary_lines", "memory")
        healthy_provider = healthy_layer.dataProvider()
        healthy_layer.startEditing()
        unhealthy_layer = QgsVectorLayer(uri, "temporary_lines", "memory")
        unhealthy_provider = unhealthy_layer.dataProvider()
        unhealthy_layer.startEditing()
        healthy_features = []
        unhealthy_features = []
        for row in segments:
            for line in row["healthy"]:
                healthy_feature = QgsFeature()
                healthy_feature.setGeometry(
                    QgsGeometry.fromPolyline([QgsPoint(line[0][0], line[0][1]), QgsPoint(line[1][0], line[1][1])])
                )
                healthy_features.append(healthy_feature)
            for line in row["unhealthy"]:
                unhealthy_feature = QgsFeature()
                unhealthy_feature.setGeometry(
                    QgsGeometry.fromPolyline([QgsPoint(line[0][0], line[0][1]), QgsPoint(line[1][0], line[1][1])])
                )
                unhealthy_features.append(unhealthy_feature)
        healthy_provider.addFeatures(healthy_features)
        healthy_layer.updateExtents()
        unhealthy_provider.addFeatures(unhealthy_features)
        unhealthy_layer.updateExtents()
        return healthy_layer, unhealthy_layer

    def name(self) -> str:
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localized.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return "crop_row_connector"

    def displayName(self) -> str:
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr("Crop Row Connector")

    def group(self) -> str:
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localized.
        """
        return self.tr(self.groupId())

    def groupId(self) -> str:
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localized.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return ""

    def tr(self, string: str) -> str:
        return QCoreApplication.translate("Processing", string)  # type: ignore[no-any-return]

    def createInstance(self) -> CropRowConnectorAlgorithm:
        return CropRowConnectorAlgorithm()
