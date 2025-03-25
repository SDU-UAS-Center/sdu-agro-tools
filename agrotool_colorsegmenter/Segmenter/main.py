from qgis.core import QgsRasterLayer, QgsProject, QgsTask, QgsMessageLog, Qgis
from osgeo import gdal
from PyQt5.QtCore import QThreadPool, pyqtSignal, QEventLoop

import time
import os
import numpy as np

from . import colormodels, segmenter, tiler, segmenter_thread



class SegmentationTask(QgsTask):
    # Custom signals to update progress and deliver the result
    progress_signal = pyqtSignal(int)
    finish_signal = pyqtSignal()

    def __init__(self, param, description="Segmentation Task"):
        super().__init__(description, QgsTask.CanCancel)
        self.param = param
        self.start_time = time.time()

    def cancel(self):  # This method is invoked when calling task.cancel() from the progress GUI
        super().cancel()
        print('CANCELATION')
        # Emit finish signal to ensure main process is shut down
        self.finish_signal.emit()
    

    def run(self):
        try:
            thread_pool = QThreadPool().globalInstance()  # Create pool of Thread
            thread_pool.setMaxThreadCount(os.cpu_count())  # Set number of cpu count

            # Initialize the color model using reference pixels
            self.progress_signal.emit(0)
            referencepixels = colormodels.get_referencepixels(self.param)
            QgsMessageLog.logMessage("Reference color model obtained.", "AgroTool Color Segmenter", level=Qgis.Info)

            # Check if the task has been cancelled
            if self.isCanceled():
                return False  # Exit early if canceled
        
            colormodel = colormodels.initialize_colormodel(referencepixels, self.param)
            cbs = segmenter.ColorBasedSegmenter(colormodel, self.param, task = self)
            #cbs = segmenter_thread.ColorBasedSegmenter(colormodel, self.param, thread_pool=thread_pool, task = self)
            cbs.progress_signal.connect(self.progress_signal.emit)
            self.progress_signal.emit(20)  # 20% progress

            # Check if the task has been cancelled
            if self.isCanceled():
                return False  # Exit early if canceled

            # Define tile object:
            tile_manager =  tiler.intilizatize_tiler_manager(thread_pool, self.param, task = self)
            tile_manager.progress_signal.connect(self.progress_signal.emit)
            QgsMessageLog.logMessage("Proceed to define the tiles.", "AgroTool Color Segmenter", level=Qgis.Info)

            if self.param.tile_processing:
                # For tile processing, generate tile list and manager
                tile_list = tiler.get_multiples_tiles(tile_manager, self.param)
                QgsMessageLog.logMessage("Multiples tiles defined.", "AgroTool Color Segmenter", level=Qgis.Info)
                
                # Check if the task has been cancelled
                if self.isCanceled():
                    return False  # Exit early if canceled

                # Apply color model
                QgsMessageLog.logMessage("Proceed to apply color model to tiles.", "AgroTool Color Segmenter", level=Qgis.Info)
                cbs.apply_colormodel_multi_tiles(tile_list)

                # Check if the task has been cancelled
                if self.isCanceled():
                    return False  # Exit early if canceled

                # cbs = segmenter_thread2.ColorBasedSegmenter(tile_list, colormodel, self.param)
                # cbs.apply_colormodel_multi_tiles_thread(thread_pool)

                # Stitch tiles back together - single distance image
                distance_image = tile_manager.get_distance_raster()

            else:
                # For single-tile processing
                single_tile = tiler.get_single_tile(tile_manager, self.param)
                QgsMessageLog.logMessage("Single tile defined.", "AgroTool Color Segmenter", level=Qgis.Info)
                self.progress_signal.emit(40)  # 40% progress

                # Check if the task has been cancelled
                if self.isCanceled():
                    return False  # Exit early if canceled

                # Apply color model
                QgsMessageLog.logMessage("Proceed to apply color model to single tile.", "AgroTool Color Segmenter", level=Qgis.Info)
                cbs.apply_colormodel_single_tile(single_tile)
                self.progress_signal.emit(80)  # 80% progress

                # Check if the task has been cancelled
                if self.isCanceled():
                    return False  # Exit early if canceled

                # Return distance image
                distance_image = np.squeeze(single_tile.distance_img)

            self.progress_signal.emit(90)  # 90% progress
            self.result_array = distance_image
        
            return True  # Indicate success
        
        except Exception as e:
            QgsMessageLog.logMessage("Error during segmentation: " + str(e), "AgroTool Color Segmenter", level=Qgis.Critical)
            return False  # Indicate failure


    def finished(self, result):
        """
        This method is called in the main thread after run() completes.
        It handles saving the result and adding the raster layer to QGIS.
        Needs to be implemented out of the QTask as it handle QGIS internal resources.
        """
        
        if result:
            QgsMessageLog.logMessage("Segmentation task finished successfully - Storing results.", "AgroTool Color Segmenter", level=Qgis.Info)
            try:
                # Create output raster layer:
                # Extract raster information using GDAL
                input_ds = gdal.Open(self.param.input_raster_layer.source())
                if input_ds is None:
                    raise RuntimeError("Failed to open input raster with GDAL.")

                # Get raster geotransform and dimensions
                geotransform = input_ds.GetGeoTransform()  
                x_res = input_ds.RasterXSize  # Number of pixels in the x-direction
                y_res = input_ds.RasterYSize  # Number of pixels in the y-direction

                # Create the output raster using the same dimensions, geotransform, and projection
                driver = gdal.GetDriverByName('GTiff')
                output_ds = driver.Create(self.param.output_file_path, x_res, y_res, 1, gdal.GDT_Byte)
                if output_ds is None:
                    raise RuntimeError("Failed to create output raster.")

                output_ds.SetGeoTransform(geotransform)  # Set the same geotransform as the input raster
                output_ds.SetProjection(input_ds.GetProjection())  # Use the same projection as the input raster

                # Save result: write array to raster and build overviews
                band = output_ds.GetRasterBand(1)
                band.SetNoDataValue(0)
                band.WriteArray(self.result_array)                # Store segmentation result
                gdal.SetConfigOption("COMPRESS_OVERVIEW", "LZW")  
                output_ds.BuildOverviews("AVERAGE", [2, 4, 8, 16, 32, 64, 128]) # Build pyramids (overviews) for the raster
                band.FlushCache()

                # Create a QgsRasterLayer from the in-memory raster
                output_name, _ = os.path.splitext(os.path.basename(self.param.output_file_path))
                output_raster_layer = QgsRasterLayer(output_ds.GetDescription(), output_name, "gdal")

                if not output_raster_layer.isValid():
                    raise RuntimeError("Failed to create QgsRasterLayer from in-memory raster.")

                # Add output raster to current project
                QgsProject.instance().addMapLayer(output_raster_layer)
                QgsMessageLog.logMessage("Task completed - distance raster added to QGIS.", "AgroTool Color Segmenter", level=Qgis.Info)
                self.progress_signal.emit(100)
                
                # Time information
                end_time = time.time()
                minutes = int((end_time - self.start_time) // 60)
                seconds = int((end_time - self.start_time) % 60)
                QgsMessageLog.logMessage(f"Total processing time: {minutes} min {seconds} sec", "AgroTool Color Segmenter", level=Qgis.Info)
                #print(f"Total processing time: {minutes} min {seconds} sec", "AgroTool Color Segmenter")   
            except Exception as e:
                QgsMessageLog.logMessage("Error while saving result: " + str(e), "AgroTool Color Segmenter", level=Qgis.Critical)
        else:
            QgsMessageLog.logMessage("Segmentation task failed.", "AgroTool Color Segmenter", level=Qgis.Critical)
        
        self.finish_signal.emit()
        return