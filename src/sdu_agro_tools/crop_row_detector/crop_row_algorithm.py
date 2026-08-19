from __future__ import annotations

import concurrent.futures
import threading
from contextlib import nullcontext
from copy import deepcopy
from functools import partial
from typing import Any

import numpy as np
import rasterio
from crop_row_detector import CropRowDetector, OrthomosaicTiles, Tile
from qgis.core import (
    Qgis,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsMessageLog,
    QgsPoint,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterVectorDestination,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QCoreApplication, QMetaType
from rasterio.enums import Resampling


class CropRowAlgorithm(QgsProcessingAlgorithm):  # type: ignore[misc]
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

    SAVE_ORTHO = "SAVE_ORTHO"
    OUTPUT_ORTHO = "OUTPUT_ORTHO"
    OUTPUT_POINTS = "OUTPUT_POINTS"
    OUTPUT_ROWS = "OUTPUT_ROWS"
    INPUT = "INPUT"
    ORTHO = "ORTHO"
    THRESHOLD = "THRESHOLD"
    VEG_THRESHOLD = "VEG_THRESHOLD"
    TILE_WIDTH = "TILE_WIDTH"
    TILE_HEIGHT = "TILE_HEIGHT"
    TILE_OVERLAP = "TILE_OVERLAP"
    TILE_BOUNDARY = "TILE_BOUNDARY"
    CROP_ROW_DISTANCE = "CROP_ROW_DISTANCE"
    MIN_ANGLE = "MIN_ANGLE"
    MAX_ANGLE = "MAX_ANGLE"
    ANGLE_RESOLUTION = "ANGLE_RESOLUTION"
    USE_PROCESS_POOL = "USE_PROCESS_POOL"

    def initAlgorithm(self, config: dict[str, Any]) -> None:
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, self.tr("Input Distance orthomosaic")))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.THRESHOLD,
                self.tr("Threshold to apply to distance orthomosaic"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=30,
                minValue=0,
                maxValue=255,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.VEG_THRESHOLD,
                self.tr("Threshold to apply to crop row point vegetation"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=30,
                minValue=0,
                maxValue=255,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TILE_WIDTH,
                self.tr("Tile Width"),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=512,
                minValue=64,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TILE_HEIGHT,
                self.tr("Tile Height"),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=512,
                minValue=64,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TILE_OVERLAP,
                self.tr("Tile Overlap as a percentage"),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=0,
                minValue=0,
                maxValue=50,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CROP_ROW_DISTANCE,
                self.tr("Initial gauss of distance between crop rows in cm"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=25,
                minValue=1,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MIN_ANGLE,
                self.tr("Min angle of crop row direction"),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=0,
                minValue=0,
                maxValue=180,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_ANGLE,
                self.tr("Max angle of crop row direction"),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=180,
                minValue=0,
                maxValue=180,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.ANGLE_RESOLUTION,
                self.tr("Number of subdivision of each degree"),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=8,
                minValue=1,
                maxValue=32,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(self.USE_PROCESS_POOL, self.tr("Use Processing Pool instead of Threads"))
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.SAVE_ORTHO,
                self.tr("Save output orthomosaic."),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.ORTHO, self.tr("Orthomosaic on which to draw crop rows"), optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.TILE_BOUNDARY,
                self.tr("Draw tile boundaries on output"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(self.OUTPUT_ORTHO, self.tr("Output orthomosaic with crop rows"))
        )
        self.addParameter(QgsProcessingParameterVectorDestination(self.OUTPUT_POINTS, self.tr("Output crop points")))
        self.addParameter(QgsProcessingParameterVectorDestination(self.OUTPUT_ROWS, self.tr("Output crop rows")))

    def prepareAlgorithm(
        self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback
    ) -> Any:
        QgsMessageLog.logMessage(
            f"Crop-row-detector called with parameters: {parameters}",
            tag="SDU Agro Tools",
            level=Qgis.MessageLevel.Info,
        )
        self.raster_input = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        self.ortho_input = self.parameterAsRasterLayer(parameters, self.ORTHO, context)
        tile_width = self.parameterAsInt(parameters, self.TILE_WIDTH, context)
        tile_height = self.parameterAsInt(parameters, self.TILE_HEIGHT, context)
        tile_overlap = self.parameterAsInt(parameters, self.TILE_OVERLAP, context) / 100
        tiler_params = {
            "orthomosaic": self.raster_input.source(),
            "tile_size": (tile_width, tile_height),
            "overlap": tile_overlap,
        }
        self.segmented_tiler = OrthomosaicTiles(**tiler_params)
        if self.ortho_input is None:
            self.plot_tiler = deepcopy(self.segmented_tiler)
        else:
            tiler_params = {
                "orthomosaic": self.ortho_input.source(),
                "tile_size": (tile_width, tile_height),
                "overlap": tile_overlap,
            }
            self.plot_tiler = OrthomosaicTiles(**tiler_params)
        return super().prepareAlgorithm(parameters, context, feedback)

    def processAlgorithm(
        self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback
    ) -> dict[str, Any]:
        use_process_pool = self.parameterAsBoolean(parameters, self.USE_PROCESS_POOL, context)
        save_raster = self.parameterAsBoolean(parameters, self.SAVE_ORTHO, context)
        if save_raster:
            raster_output = self.parameterAsOutputLayer(parameters, self.OUTPUT_ORTHO, context)
        else:
            raster_output = None
        points_output = self.parameterAsOutputLayer(parameters, self.OUTPUT_POINTS, context)
        rows_output = self.parameterAsOutputLayer(parameters, self.OUTPUT_ROWS, context)
        self.segmented_tiler.divide_orthomosaic_into_tiles()
        self.plot_tiler.divide_orthomosaic_into_tiles()
        crd = CropRowDetector()
        crd.tile_boundary = self.parameterAsBool(parameters, self.TILE_BOUNDARY, context)
        crd.expected_crop_row_distance_cm = self.parameterAsDouble(parameters, self.CROP_ROW_DISTANCE, context)
        if crd.expected_crop_row_distance is None:
            crd.convert_crop_row_distance_to_pixels(
                self.segmented_tiler.get_orthomosaic_res(), self.segmented_tiler.get_orthomosaic_crs()
            )
        crd.min_crop_row_angle = self.parameterAsInt(parameters, self.MIN_ANGLE, context)
        crd.max_crop_row_angle = self.parameterAsInt(parameters, self.MAX_ANGLE, context)
        crd.crop_row_angle_division = self.parameterAsInt(parameters, self.ANGLE_RESOLUTION, context)
        crd.threshold_level = self.parameterAsDouble(parameters, self.THRESHOLD, context)
        crd.max_workers = context.maximumThreads()
        if feedback.isCanceled():
            return {}
        if use_process_pool:
            return self.run_using_processing_pools(crd, raster_output, points_output, rows_output, context, feedback)
        else:
            return self.run_using_threads(crd, raster_output, points_output, rows_output, context, feedback)

    def run_using_processing_pools(
        self,
        crd: CropRowDetector,
        raster_output: str | None,
        points_output: str | None,
        rows_output: str | None,
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, Any]:
        segmented_tiles = self.segmented_tiler.tiles
        plot_tiles = self.plot_tiler.tiles
        total = 100.0 / len(segmented_tiles)
        with rasterio.open(self.plot_tiler.orthomosaic) as src:
            profile = src.profile
            crs = src.crs.to_string()
            overview_factors = src.overviews(src.indexes[0])
        tiles = []
        lines_uri = f"LineString?crs={crs}"
        lines_layer = QgsVectorLayer(lines_uri, "temporary_lines", "memory")
        lines_provider = lines_layer.dataProvider()
        lines_layer.startEditing()
        lines_provider.addAttributes(
            [
                QgsField("tile", QMetaType.Type.Int),
                QgsField("x_position", QMetaType.Type.Int),
                QgsField("y_position", QMetaType.Type.Int),
                QgsField("angle", QMetaType.Type.Double),
                QgsField("row", QMetaType.Type.Int),
                QgsField("x_start", QMetaType.Type.Double),
                QgsField("y_start", QMetaType.Type.Double),
                QgsField("x_end", QMetaType.Type.Double),
                QgsField("y_end", QMetaType.Type.Double),
                QgsField("x_mid", QMetaType.Type.Double),
                QgsField("y_mid", QMetaType.Type.Double),
            ]
        )
        lines_layer.updateFields()
        points_uri = f"Point?crs={crs}"
        points_layer = QgsVectorLayer(points_uri, "temporary_points", "memory")
        points_provider = points_layer.dataProvider()
        points_layer.startEditing()
        points_provider.addAttributes(
            [
                QgsField("tile", QMetaType.Type.Int),
                QgsField("row", QMetaType.Type.Int),
                QgsField("x", QMetaType.Type.Double),
                QgsField("y", QMetaType.Type.Double),
                QgsField("vegetation", QMetaType.Type.Double),
            ]
        )
        points_layer.updateFields()
        with concurrent.futures.ProcessPoolExecutor(max_workers=context.maximumThreads()) as executor:
            for current, result in enumerate(
                executor.map(partial(process_in_pools, crd=crd), segmented_tiles, plot_tiles)
            ):
                if feedback.isCanceled():
                    return {}
                feedback.setProgress(int(current * total))
                tile = result[0]
                direction = result[1]
                vegetation_lines = result[2]
                vegetation_df = result[3]
                tiles.append(tile)
                if direction < 0:
                    direction = np.pi + direction
                line_features = []
                for row_number, row in enumerate(vegetation_lines):
                    x_start = tile.ulc_global[0] + tile.resolution[0] * row[0][0]
                    y_start = tile.ulc_global[1] - tile.resolution[1] * row[0][1]
                    x_end = tile.ulc_global[0] + tile.resolution[0] * row[1][0]
                    y_end = tile.ulc_global[1] - tile.resolution[1] * row[1][1]
                    x_mid = (2 * tile.ulc_global[0] + tile.resolution[0] * (row[0][0] + row[1][0])) / 2
                    y_mid = (2 * tile.ulc_global[1] - tile.resolution[1] * (row[0][1] + row[1][1])) / 2
                    line_feature = QgsFeature()
                    line_feature.setGeometry(
                        QgsGeometry.fromPolyline([QgsPoint(x_start, y_start), QgsPoint(x_end, y_end)])
                    )
                    line_feature.setAttributes(
                        [
                            int(tile.tile_number),
                            tile.tile_position[0],
                            tile.tile_position[1],
                            direction,
                            row_number,
                            x_start,
                            y_start,
                            x_end,
                            y_end,
                            x_mid,
                            y_mid,
                        ]
                    )
                    line_features.append(line_feature)
                lines_provider.addFeatures(line_features)
                point_features = []
                for row in vegetation_df.itertuples(index=False):
                    point_feature = QgsFeature()
                    point_feature.setGeometry(QgsGeometry.fromPoint(QgsPoint(row.x, row.y)))
                    point_feature.setAttributes([row.tile, row.row, row.x, row.y, row.vegetation])
                    point_features.append(point_feature)
                points_provider.addFeatures(point_features)
        lines_layer.updateExtents()
        points_layer.updateExtents()
        if raster_output is not None:
            with rasterio.open(raster_output, "w", **profile) as dst:
                for tile in tiles:
                    dst.write(tile.output, window=tile.window)
                    if tile.output.shape[0] <= 3:
                        dst.write_mask(tile.mask, window=tile.window)
            with rasterio.open(raster_output, "r+") as dst:
                dst.build_overviews(overview_factors, Resampling.average)
        points_layer.setSubsetString("vegetation > 50")
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.layerName = "Crop Points"
        QgsVectorFileWriter.writeAsVectorFormatV3(
            points_layer, points_output, QgsProject.instance().transformContext(), options=options
        )
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.layerName = "Crop Rows"
        QgsVectorFileWriter.writeAsVectorFormatV3(
            lines_layer, rows_output, QgsProject.instance().transformContext(), options=options
        )
        return {self.OUTPUT_ORTHO: raster_output, self.OUTPUT_POINTS: points_output, self.OUTPUT_ROWS: rows_output}

    def run_using_threads(
        self,
        crd: CropRowDetector,
        raster_output: str | None,
        points_output: str | None,
        rows_output: str | None,
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, Any]:
        segmented_tiles = self.segmented_tiler.tiles
        plot_tiles = self.plot_tiler.tiles
        read_segmented_lock = threading.Lock()
        read_plot_lock = threading.Lock()
        write_lock = threading.Lock()
        row_info_global_lock = threading.Lock()
        row_vegetation_lock = threading.Lock()
        process_lock = threading.Lock()
        total = 100.0 / len(segmented_tiles)
        with (
            rasterio.open(self.plot_tiler.orthomosaic) as plot_src,
            rasterio.open(self.segmented_tiler.orthomosaic) as segmented_src,
        ):
            profile = plot_src.profile
            crs = segmented_src.crs.to_string()
            overview_factors = plot_src.overviews(plot_src.indexes[0])
            lines_uri = f"LineString?crs={crs}"
            lines_layer = QgsVectorLayer(lines_uri, "temporary_lines", "memory")
            lines_provider = lines_layer.dataProvider()
            lines_layer.startEditing()
            lines_provider.addAttributes(
                [
                    QgsField("tile", QMetaType.Type.Int),
                    QgsField("x_position", QMetaType.Type.Int),
                    QgsField("y_position", QMetaType.Type.Int),
                    QgsField("angle", QMetaType.Type.Double),
                    QgsField("row", QMetaType.Type.Int),
                    QgsField("x_start", QMetaType.Type.Double),
                    QgsField("y_start", QMetaType.Type.Double),
                    QgsField("x_end", QMetaType.Type.Double),
                    QgsField("y_end", QMetaType.Type.Double),
                    QgsField("x_mid", QMetaType.Type.Double),
                    QgsField("y_mid", QMetaType.Type.Double),
                ]
            )
            lines_layer.updateFields()
            points_uri = f"Point?crs={crs}"
            points_layer = QgsVectorLayer(points_uri, "temporary_points", "memory")
            points_provider = points_layer.dataProvider()
            points_layer.startEditing()
            points_provider.addAttributes(
                [
                    QgsField("tile", QMetaType.Type.Int),
                    QgsField("row", QMetaType.Type.Int),
                    QgsField("x", QMetaType.Type.Double),
                    QgsField("y", QMetaType.Type.Double),
                    QgsField("vegetation", QMetaType.Type.Double),
                ]
            )
            points_layer.updateFields()
            with rasterio.open(raster_output, "w", **profile) if raster_output is not None else nullcontext() as dst:

                def process(segmented_tile: Tile, plot_tile: Tile) -> None:
                    with read_segmented_lock:
                        segmented_img = segmented_src.read(window=segmented_tile.window_with_overlap)
                    with read_plot_lock:
                        plot_img = plot_src.read(window=plot_tile.window_with_overlap)
                        if plot_img.shape[0] > 3:
                            mask = None
                        else:
                            mask_temp = plot_src.read_masks(window=plot_tile.window_with_overlap)
                            mask = mask_temp[0]
                            for band in range(mask_temp.shape[0]):
                                mask = mask & mask_temp[band]
                    with process_lock:
                        output_img, direction, vegetation_lines, vegetation_df = crd.detect_crop_rows(
                            segmented_img, segmented_tile, plot_img, plot_tile
                        )
                    with row_info_global_lock:
                        line_features = []
                        for row_number, row in enumerate(vegetation_lines):
                            x_start = plot_tile.ulc_global[0] + plot_tile.resolution[0] * row[0][0]
                            y_start = plot_tile.ulc_global[1] - plot_tile.resolution[1] * row[0][1]
                            x_end = plot_tile.ulc_global[0] + plot_tile.resolution[0] * row[1][0]
                            y_end = plot_tile.ulc_global[1] - plot_tile.resolution[1] * row[1][1]
                            x_mid = (
                                2 * plot_tile.ulc_global[0] + plot_tile.resolution[0] * (row[0][0] + row[1][0])
                            ) / 2
                            y_mid = (
                                2 * plot_tile.ulc_global[1] - plot_tile.resolution[1] * (row[0][1] + row[1][1])
                            ) / 2
                            line_feature = QgsFeature()
                            line_feature.setGeometry(
                                QgsGeometry.fromPolyline([QgsPoint(x_start, y_start), QgsPoint(x_end, y_end)])
                            )
                            line_feature.setAttributes(
                                [
                                    int(plot_tile.tile_number),
                                    plot_tile.tile_position[0],
                                    plot_tile.tile_position[1],
                                    direction,
                                    row_number,
                                    x_start,
                                    y_start,
                                    x_end,
                                    y_end,
                                    x_mid,
                                    y_mid,
                                ]
                            )
                            line_features.append(line_feature)
                        lines_provider.addFeatures(line_features)
                    with row_vegetation_lock:
                        point_features = []
                        for row in vegetation_df.itertuples(index=False):
                            point_feature = QgsFeature()
                            point_feature.setGeometry(QgsGeometry.fromPoint(QgsPoint(row.x, row.y)))
                            point_feature.setAttributes([row.tile, row.row, row.x, row.y, row.vegetation])
                            point_features.append(point_feature)
                        points_provider.addFeatures(point_features)
                    output = plot_tile.get_window_pixels(output_img)
                    if mask is not None:
                        mask = plot_tile.get_window_pixels(np.expand_dims(mask, 0)).squeeze()
                    with write_lock:
                        if dst is not None:
                            dst.write(output, window=plot_tile.window)
                            if mask is not None:
                                dst.write_mask(mask, window=plot_tile.window)

                with concurrent.futures.ThreadPoolExecutor(max_workers=context.maximumThreads()) as executor:
                    for current, _ in enumerate(executor.map(process, segmented_tiles, plot_tiles)):
                        if feedback.isCanceled():
                            return {}
                        feedback.setProgress(int(current * total))
        if raster_output is not None:
            with rasterio.open(raster_output, "r+") as dst:
                dst.build_overviews(overview_factors, Resampling.average)
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.layerName = "Crop Points"
        QgsVectorFileWriter.writeAsVectorFormatV3(
            points_layer, points_output, QgsProject.instance().transformContext(), options=options
        )
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.layerName = "Crop Rows"
        QgsVectorFileWriter.writeAsVectorFormatV3(
            lines_layer, rows_output, QgsProject.instance().transformContext(), options=options
        )
        return {self.OUTPUT_ORTHO: raster_output, self.OUTPUT_POINTS: points_output, self.OUTPUT_ROWS: rows_output}

    def name(self) -> str:
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localized.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return "crop_row_detector"

    def displayName(self) -> str:
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr("Crop Row Detector")

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

    def createInstance(self) -> CropRowAlgorithm:
        return CropRowAlgorithm()


def process_in_pools(
    segmented_tile: Tile, plot_tile: Tile, crd: CropRowDetector | None = None
) -> tuple[Tile, Any, Any, Any]:
    if crd is None:
        raise ValueError("crd must be set to a instance if CropRowDetector")
    segmented_image, _ = segmented_tile.read_tile()
    plot_image, plot_mask = plot_tile.read_tile()
    mask = plot_mask[0]
    for band in range(plot_mask.shape[0]):
        mask = mask & plot_mask[band]
    output_img, direction, vegetation_lines, vegetation_df = crd.detect_crop_rows(
        segmented_image, segmented_tile, plot_image, plot_tile
    )
    output = plot_tile.get_window_pixels(output_img)
    mask = plot_tile.get_window_pixels(np.expand_dims(mask, 0)).squeeze()
    plot_tile.output = output
    plot_tile.mask = mask
    return plot_tile, direction, vegetation_lines, vegetation_df
