from __future__ import annotations

import concurrent.futures
import inspect
import os
import threading
from typing import Any

import CDC
import numpy as np
import rasterio
from qgis import processing
from qgis.core import (
    Qgis,
    QgsMessageLog,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingParameterBand,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterString,
)
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from rasterio.enums import Resampling


class CDCAlgorithm(QgsProcessingAlgorithm):  # type: ignore[misc]
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

    OUTPUT = "OUTPUT"
    INPUT = "INPUT"
    BANDS = "BANDS"
    REF_TYPE = "REF_TYPE"
    REFERENCE = "REFERENCE"
    ANNOTATED = "ANNOTATED"
    SHAPE_FILE = "SHAPE_FILE"
    SCALE = "SCALE"
    TILE_WIDTH = "TILE_WIDTH"
    TILE_HEIGHT = "TILE_HEIGHT"
    TILE_OVERLAP = "TILE_OVERLAP"
    COLOR_MODEL = "COLOR_MODEL"
    GMM_PARAM = "GMM_PARAM"

    TRANSFORM = "TRANSFORM"
    LAMBDA = "LAMBDA"
    GAMMA = "GAMMA"

    CONVERT_UINT = "CONTERT_UINT"

    def initAlgorithm(self, config: dict[str, Any]) -> None:
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """
        self.ref_type_choices = ["Shape File", "Reference Images"]
        self.color_model_choices = ["Mahalanobis", "Gaussian Mixture Model"]
        self.transform_choices = ["No transform", "Lambda expression", "Gamma"]

        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, self.tr("Input layer")))
        self.addParameter(
            QgsProcessingParameterBand(
                self.BANDS,
                self.tr("Bands to use for Color"),
                allowMultiple=True,
                parentLayerParameterName=self.INPUT,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.REF_TYPE,
                self.tr("Reference type"),
                self.ref_type_choices,
                allowMultiple=False,
                defaultValue=0,
            )
        )
        self.addParameter(QgsProcessingParameterRasterLayer(self.REFERENCE, self.tr("Reference Image"), optional=True))
        self.addParameter(
            QgsProcessingParameterRasterLayer(self.ANNOTATED, self.tr("Reference Image Annotated"), optional=True)
        )
        self.addParameter(QgsProcessingParameterFeatureSource(self.SHAPE_FILE, self.tr("Shape file"), optional=True))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.COLOR_MODEL,
                self.tr("Color Model"),
                self.color_model_choices,
                allowMultiple=False,
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.GMM_PARAM,
                self.tr("GMM parameters"),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=2,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SCALE,
                self.tr("Scale"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=5,
                minValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TILE_WIDTH,
                self.tr("Tile Width"),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=2048,
                minValue=64,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TILE_HEIGHT,
                self.tr("Tile Height"),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=2048,
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
            QgsProcessingParameterEnum(
                self.TRANSFORM,
                self.tr("Transform to apply to input"),
                self.transform_choices,
                allowMultiple=False,
                defaultValue=0,
            )
        )
        self.addParameter(QgsProcessingParameterString(self.LAMBDA, self.tr("Python Lambda Expression"), optional=True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.GAMMA,
                self.tr("Gamma value for the gamma transform"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.5,
                minValue=0,
                maxValue=5,
                optional=True,
            )
        )
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, self.tr("Output Color Distance Layer")))
        self.addParameter(
            QgsProcessingParameterBoolean(self.CONVERT_UINT, self.tr("Convert result to uint8"), defaultValue=True)
        )

    def prepareAlgorithm(
        self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback
    ) -> Any:
        self.raster_input = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        self.raster_bands = self.parameterAsInts(parameters, self.BANDS, context)
        if not self.raster_bands:
            self.raster_bands = None
        else:
            if len(self.raster_bands) < 2:
                QgsMessageLog.logMessage(
                    f"At least 2 bands must be used. CDC called with {len(self.raster_bands)} bands.",
                    tag="SDU Agro Tools",
                    level=Qgis.MessageLevel.Warning,
                )
                raise ValueError(f"At least 2 bands must be used. CDC called with {len(self.raster_bands)} bands.")
            self.raster_bands = [x - 1 for x in self.raster_bands]
        self.scale = self.parameterAsDouble(parameters, self.SCALE, context)
        tile_width = self.parameterAsInt(parameters, self.TILE_WIDTH, context)
        tile_height = self.parameterAsInt(parameters, self.TILE_HEIGHT, context)
        tile_overlap = self.parameterAsInt(parameters, self.TILE_OVERLAP, context) / 100
        self.transform = self.parameterAsEnum(parameters, self.TRANSFORM, context)
        if self.transform == 0:
            self.transform = None
        elif self.transform == 1:
            lambda_exp = self.parameterAsString(parameters, self.LAMBDA, context)
            self.transform = CDC.LambdaTransform(lambda_exp)
        elif self.transform == 2:
            gamma = self.parameterAsDouble(parameters, self.GAMMA, context)
            self.transform = CDC.GammaTransform(gamma)
        self.ref_type = self.parameterAsEnum(parameters, self.REF_TYPE, context)
        self.color_model_params = self.parameterAsEnum(parameters, self.COLOR_MODEL, context)
        self.gmm_params = self.parameterAsInt(parameters, self.GMM_PARAM, context)
        tiler_params = {
            "orthomosaic": self.raster_input.source(),
            "tile_size": (tile_width, tile_height),
            "overlap": tile_overlap,
        }
        self.tiler = CDC.OrthomosaicTiles(**tiler_params)
        self.convert_uint8 = self.parameterAsBoolean(parameters, self.CONVERT_UINT, context)
        return super().prepareAlgorithm(parameters, context, feedback)

    def processAlgorithm(
        self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback
    ) -> dict[str, Any]:
        raster_output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        if self.ref_type == 1:
            reference = self.parameterAsRasterLayer(parameters, self.REFERENCE, context)
            annotated = self.parameterAsRasterLayer(parameters, self.ANNOTATED, context)
            color_params = {
                "reference": reference.source(),
                "annotated": annotated.source(),
                "bands_to_use": self.raster_bands,
                "transform": self.transform,
            }
            if self.color_model_params == 0:
                color_model = CDC.MahalanobisDistance.from_image_annotation(**color_params)
            elif self.color_model_params == 1:
                color_params.update({"n_components": self.gmm_params})
                color_model = CDC.GaussianMixtureModelDistance.from_image_annotation(**color_params)
        elif self.ref_type == 0:
            pixel_centroids_params = {
                "INPUT_RASTER": self.raster_input.source(),
                "INPUT_VECTOR": parameters[self.SHAPE_FILE],
                "OUTPUT": "TEMPORARY_OUTPUT",
            }
            pixel_centroids = processing.run(
                "native:generatepointspixelcentroidsinsidepolygons",
                pixel_centroids_params,
                context=context,
                feedback=feedback,
                is_child_algorithm=True,
            )
            pixel_values_params = {
                "INPUT": pixel_centroids["OUTPUT"],
                "RASTERCOPY": self.raster_input.source(),
                "OUTPUT": "TEMPORARY_OUTPUT",
            }
            pixel_values = processing.run(
                "native:rastersampling",
                pixel_values_params,
                context=context,
                feedback=feedback,
                is_child_algorithm=True,
            )
            pixel_values = self.parameterAsSource(pixel_values, "OUTPUT", context)
            pixel_values_list = []
            for x in pixel_values.getFeatures():
                pixel_values_list.append(x.attributes())
            pixel_value = np.array(pixel_values_list).transpose()
            pixel_value = pixel_value[3:, :]
            color_params = {
                "pixel_values": pixel_value,
                "bands_to_use": self.raster_bands,
                "transform": self.transform,
            }
            if self.color_model_params == 0:
                color_model = CDC.MahalanobisDistance.from_pixel_values(**color_params)
            elif self.color_model_params == 1:
                color_params.update({"n_components": self.gmm_params})
                color_model = CDC.GaussianMixtureModelDistance.from_pixel_values(**color_params)
        self.tiler.divide_orthomosaic_into_tiles()
        if feedback.isCanceled():
            return {}
        total = 100.0 / len(self.tiler.tiles)
        read_lock = threading.Lock()
        process_lock = threading.Lock()
        write_lock = threading.Lock()
        with rasterio.open(self.raster_input.source()) as src:
            profile = src.profile
            profile["count"] = 1
            if not self.convert_uint8:
                profile.update(dtype="float64")
            overview_factors = src.overviews(src.indexes[0])
            with rasterio.open(raster_output, "w", **profile) as dst:

                def process(tile: CDC.Tile) -> None:
                    with read_lock:
                        img = src.read(window=tile.window_with_overlap)
                        mask_temp = src.read_masks(window=tile.window_with_overlap)
                    mask = mask_temp[0]
                    for band in range(mask_temp.shape[0]):
                        mask = mask & mask_temp[band]
                    with process_lock:
                        distance_image = color_model.calculate_distance(img)
                    if self.convert_uint8:
                        distance = np.minimum(np.abs(self.scale * distance_image), 255)
                        distance = distance.astype(np.uint8)
                    else:
                        distance = distance_image
                    output = tile.get_window_pixels(distance)
                    mask = tile.get_window_pixels(np.expand_dims(mask, 0)).squeeze()
                    with write_lock:
                        dst.write(output, window=tile.window)
                        dst.write_mask(mask, window=tile.window)

                with concurrent.futures.ThreadPoolExecutor(max_workers=context.maximumThreads()) as executor:
                    for current, _ in enumerate(executor.map(process, self.tiler.tiles)):
                        if feedback.isCanceled():
                            return {}
                        feedback.setProgress(int(current * total))
        with rasterio.open(raster_output, "r+") as dst:
            dst.build_overviews(overview_factors, Resampling.average)
        return {self.OUTPUT: raster_output}

    def name(self) -> str:
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return "color_distance_calculator"

    def displayName(self) -> str:
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr("Color Distance Calculator")

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

    def createInstance(self) -> CDCAlgorithm:
        return CDCAlgorithm()

    def icon(self) -> QIcon:
        cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]  # type: ignore[arg-type]
        icon = QIcon(os.path.join(os.path.join(cmd_folder, "icon.png")))
        return icon
