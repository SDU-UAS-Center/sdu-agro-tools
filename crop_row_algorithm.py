from __future__ import annotations

import concurrent.futures
import inspect
import os
import threading
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import rasterio
from crop_row_detector import CropRowDetector, OrthomosaicTiles, Tile
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterVectorDestination,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from rasterio.enums import Resampling
from shapely import linestrings
from shapely.geometry.linestring import LineString


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

    OUTPUT_ORTHO = "OUTPUT_ORTHO"
    OUTPUT_SHAPE = "OUTPUT_SHAPE"
    OUTPUT_FOLDER = "OUTPUT_FOLDER"
    INPUT = "INPUT"
    ORTHO = "ORTHO"
    THRESHOLD = "THRESHOLD"
    TILE_WIDTH = "TILE_WIDTH"
    TILE_HEIGHT = "TILE_HEIGHT"
    TILE_OVERLAP = "TILE_OVERLAP"
    TILE_BOUNDARY = "TILE_BOUNDARY"
    CROP_ROW_DISTANCE = "CROP_ROW_DISTANCE"
    MIN_ANGLE = "MIN_ANGLE"
    MAX_ANGLE = "MAX_ANGLE"
    ANGLE_RESOLUTION = "ANGLE_RESOLUTION"
    SAVE_STATS = "SAVE_STATS"
    SAVE_STATS_LOCATION = "SAVE_STATS_LOCATION"
    USE_PROCESS_POOL = "USE_PROCESS_POOL"

    def initAlgorithm(self, config: dict[str, Any]) -> None:
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """
        self.ref_type_choices = ["Shape File", "Reference Images"]
        self.color_model_choices = ["Mahalanobis", "Gaussian Mixture Model"]
        self.transform_choices = ["No transform", "Lambda expression", "Gamma"]

        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, self.tr("Input Distance orthomosaic")))
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.ORTHO, self.tr("Orthomosaic on which to draw crop rows"), optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.THRESHOLD,
                self.tr("Threshold to apply to distance orthomosaic"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=12,
                minValue=1,
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
            QgsProcessingParameterBoolean(
                self.TILE_BOUNDARY,
                self.tr("Draw tile boundaries on output"),
                defaultValue=False,
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
            QgsProcessingParameterBoolean(
                self.SAVE_STATS,
                self.tr("Save statistics"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.SAVE_STATS_LOCATION,
                self.tr("Stats location"),
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(self.USE_PROCESS_POOL, self.tr("Use Processing Pool instead of Threads"))
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(self.OUTPUT_ORTHO, self.tr("Output orthomosaic with crop rows"))
        )
        self.addParameter(QgsProcessingParameterVectorDestination(self.OUTPUT_SHAPE, self.tr("Output crop rows")))
        self.addParameter(QgsProcessingParameterFolderDestination(self.OUTPUT_FOLDER, self.tr("Output folder")))

    def prepareAlgorithm(
        self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback
    ) -> Any:
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
        raster_output = self.parameterAsOutputLayer(parameters, self.OUTPUT_ORTHO, context)
        vector_output = self.parameterAsOutputLayer(parameters, self.OUTPUT_SHAPE, context)
        output_folder = Path(self.parameterAsFileOutput(parameters, self.OUTPUT_FOLDER, context))
        if not os.path.isdir(output_folder):
            os.makedirs(output_folder)
        self.segmented_tiler.divide_orthomosaic_into_tiles()
        self.plot_tiler.divide_orthomosaic_into_tiles()
        crd = CropRowDetector()
        crd.output_location = output_folder
        crd.tile_boundary = self.parameterAsBool(parameters, self.TILE_BOUNDARY, context)
        crd.expected_crop_row_distance_cm = self.parameterAsDouble(parameters, self.CROP_ROW_DISTANCE, context)
        crd.min_crop_row_angle = self.parameterAsInt(parameters, self.MIN_ANGLE, context)
        crd.max_crop_row_angle = self.parameterAsInt(parameters, self.MAX_ANGLE, context)
        crd.crop_row_angle_resolution = self.parameterAsInt(parameters, self.ANGLE_RESOLUTION, context)
        crd.threshold_level = self.parameterAsDouble(parameters, self.THRESHOLD, context)
        crd.max_workers = context.maximumThreads()
        use_process_pool = self.parameterAsBoolean(parameters, self.USE_PROCESS_POOL, context)
        if feedback.isCanceled():
            return {}
        if use_process_pool:
            return self.run_using_processing_pools(crd, raster_output, vector_output, context, feedback)
        else:
            return self.run_using_threads(crd, raster_output, vector_output, context, feedback)

    def run_using_processing_pools(
        self,
        crd: CropRowDetector,
        raster_output: str,
        vector_output: str,
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, Any]:
        segmented_tiles = self.segmented_tiler.tiles
        plot_tiles = self.plot_tiler.tiles
        total = 100.0 / len(segmented_tiles)
        with rasterio.open(self.plot_tiler.orthomosaic) as src:
            profile = src.profile
            overview_factors = src.overviews(src.indexes[0])
        tiles = []
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
                crd.append_to_csv_of_row_information(tile, direction, vegetation_lines)
                crd.append_to_csv_of_row_information_global(tile, direction, vegetation_lines)
                crd.append_to_csv_vegetation_row(vegetation_df)
        with rasterio.open(raster_output, "w", **profile) as dst:
            for tile in tiles:
                dst.write(tile.output, window=tile.window)
                if tile.output.shape[0] <= 3:
                    dst.write_mask(tile.mask, window=tile.window)
        with rasterio.open(raster_output, "r+") as dst:
            dst.build_overviews(overview_factors, Resampling.average)
        return {self.OUTPUT_ORTHO: raster_output}

    def run_using_threads(
        self,
        crd: CropRowDetector,
        raster_output: str,
        vector_output: str,
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, Any]:
        segmented_tiles = self.segmented_tiler.tiles
        plot_tiles = self.plot_tiler.tiles
        crd.prepare_csv_files()
        read_segmented_lock = threading.Lock()
        read_plot_lock = threading.Lock()
        write_lock = threading.Lock()
        row_info_lock = threading.Lock()
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
            with rasterio.open(raster_output, "w", **profile) as dst:

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
                    with row_info_lock:
                        crd.append_to_csv_of_row_information(plot_tile, direction, vegetation_lines)
                    with row_info_global_lock:
                        crd.append_to_csv_of_row_information_global(plot_tile, direction, vegetation_lines)
                    with row_vegetation_lock:
                        crd.append_to_csv_vegetation_row(vegetation_df)
                    output = plot_tile.get_window_pixels(output_img)
                    if mask is not None:
                        mask = plot_tile.get_window_pixels(np.expand_dims(mask, 0)).squeeze()
                    with write_lock:
                        dst.write(output, window=plot_tile.window)
                        if mask is not None:
                            dst.write_mask(mask, window=plot_tile.window)

                with concurrent.futures.ThreadPoolExecutor(max_workers=context.maximumThreads()) as executor:
                    for current, _ in enumerate(executor.map(process, segmented_tiles, plot_tiles)):
                        if feedback.isCanceled():
                            return {}
                        feedback.setProgress(int(current * total))
        with rasterio.open(raster_output, "r+") as dst:
            dst.build_overviews(overview_factors, Resampling.average)
        self.make_wkt_field_csv(crd.output_location.joinpath("row_information_global.csv"))
        line_uri = f"file://{crd.output_location.joinpath('row_information_global.csv')}?type=csv&wktField=linestrings&crs={crs}"
        line_layer = QgsVectorLayer(line_uri, "Crop Rows", "delimitedtext")
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.layerName = "Crop Rows"
        QgsVectorFileWriter.writeAsVectorFormatV3(
            line_layer, vector_output, QgsProject.instance().transformContext(), options=options
        )
        return {self.OUTPUT_ORTHO: raster_output, self.OUTPUT_SHAPE: vector_output}

    def make_wkt_field_csv(self, csv_file: Path) -> None:
        def make_lines(row: Any) -> LineString:
            line = linestrings([[row["x_start"], row["y_start"]], [row["x_end"], row["y_end"]]])
            return line

        data = pd.read_csv(csv_file)
        data["linestrings"] = data.apply(make_lines, axis="columns")
        data.to_csv(csv_file)

    def name(self) -> str:
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
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
        should be localised.
        """
        return self.tr(self.groupId())

    def groupId(self) -> str:
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return "Raster layer tools"

    def tr(self, string: str) -> str:
        return QCoreApplication.translate("Processing", string)  # type: ignore[no-any-return]

    def createInstance(self) -> CropRowAlgorithm:
        return CropRowAlgorithm()

    def icon(self) -> QIcon:
        cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]  # type: ignore[arg-type]
        icon = QIcon(os.path.join(os.path.join(cmd_folder, "icon.png")))
        return icon


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
