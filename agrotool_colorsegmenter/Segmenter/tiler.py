# -*- coding: utf-8 -*-
import numpy as np
import rasterio
import math

from rasterio.transform import Affine
import os
from qgis.core import QgsRasterLayer, QgsRaster, QgsRasterBlock, QgsProject, QgsRectangle
from osgeo import gdal
from qgis.core import QgsProcessingException, QgsMessageLog
from PyQt5.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject, pyqtSlot

from multiprocessing import shared_memory


def get_tilelist_gdal(thread_pool, output_raster_layer, param):
    # Init Tiles multiworker
    tile_manager = MultiTilesManager(thread_pool, 
                                     raster_layer = param.input_raster_layer, 
                                     output_raster_layer = output_raster_layer, 
                                     tile_size = (param.tiles_width, param.tiles_height), 
                                     overlap = param.overlap, 
                                     bands_to_use = param.bands_to_use, 
                                     output_dir=param.save_tiles_path)

    # Define multiple tiles:
    tile_manager.define_multiples_tiles_pixel()

    # Convert raster to np array
    tile_manager.extract_array_from_tile()

    if param.save_tiles == True:
        tile_manager.save_tiles()
    

    return tile_manager.get_tiles(), tile_manager

def get_single_tile(param):
    raster_layer = param.input_raster_layer

    # Load raster as GDAL object:
    gdal_raster = gdal.Open(raster_layer.source())
    if not gdal_raster:
        raise QgsProcessingException('Invalid raster layer!')
    
    resolution = [raster_layer.rasterUnitsPerPixelX(),
                  raster_layer.rasterUnitsPerPixelY()]
    # Get raster dimensions
    raster_columns = gdal_raster.RasterXSize  # Number of columns (width in pixels)
    raster_rows = gdal_raster.RasterYSize    # Number of rows (height in pixels)

    # Get geotransform to define the geographic extent
    geotransform = gdal_raster.GetGeoTransform()
    origin_x, pixel_width, _, origin_y, _, pixel_height = geotransform

    # Calculate geographic extent
    min_x = origin_x
    max_x = origin_x + pixel_width * raster_columns
    max_y = origin_y
    min_y = origin_y + pixel_height * raster_rows

    extension_geo = QgsRectangle(min_x, min_y, max_x, max_y)

    # Calculate pixel extent (extension_pixel)
    xoff = 0
    yoff = 0
    xend = raster_columns
    yend = raster_rows

    extension_pixel = QgsRectangle(xoff, yoff, xend, yend)

    # Create a Tile object
    tile = Tile(
        extension_geo,         # Geographic extent
        extension_pixel,       # Pixel extent
        [0, 0],                # Tile position (row, column)
        raster_rows,           # Tile height (entire raster)
        raster_columns,        # Tile width (entire raster)
        resolution,      # Resolution
        raster_layer.crs(),    # Coordinate Reference System (CRS)
        min_x,                 # Left extent (geographic)
        max_y,                 # Top extent (geographic)
        gdal_raster.RasterCount  # Number of bands in the raster
    )

    # Read array from the raster for the tile
    tile.read_array_from_tile(gdal_raster)

    return tile

class MultiTilesManager:
    '''
    This class receive the raster layer as input and define the tiles over it.
        1- Determine tiles pixels boundaries (over raster pixel) -> Sequential
        2- Create Tiles object: Tiles properties + tile np.array
    '''
    def __init__(self, thread_pool, raster_layer: QgsRaster, output_raster_layer : gdal.Band, tile_size, overlap, bands_to_use = None, output_dir = None):
        
        self.output_dir = output_dir

        # QGIS multiprocessing
        self.thread_pool = thread_pool

        # Save Tiles dimensions:
        if isinstance(tile_size, tuple):
            self.tile_heigth = tile_size[0]
            self.tile_width = tile_size[1]
        elif isinstance(tile_size, int):
            self.tile_heigth = tile_size
            self.tile_width = tile_size
        else:
            raise QgsProcessingException('tile_size type must be tuple or int')
        
        # TODO: Check following attributes:
        self.run_specific_tile = None
        self.run_specific_tileset = None

        # Store raster layer:
        self.raster_layer = raster_layer
        self.output_raster_layer = output_raster_layer

        # Ensure valid raster layer:
        if not self.raster_layer.isValid():
            raise QgsProcessingException('Unvalid raster layer!')
        
        # Get number of bands:
        if bands_to_use == None:
            self.n_bands = self.raster_layer.bandCount() # Number of color bands
        else:
            self.n_bands = len(bands_to_use)

        # Obtain raster information
        self.resolution = [self.raster_layer.rasterUnitsPerPixelX(),
                           self.raster_layer.rasterUnitsPerPixelY()]
        
        self.crs = self.raster_layer.crs().authid() # EPGS Coordinate System

        self.extent = self.raster_layer.extent()    # QgsRectangle
        self.left = self.extent.xMinimum()
        self.top = self.extent.yMaximum()

        # Calculate the number of rows and columns based on the raster's height and width
        self.raster_columns = raster_layer.width()
        self.raster_rows =  raster_layer.height()

        self.overlap = overlap

        # Load raster as GDAL object:
        gdal_raster = gdal.Open(self.raster_layer.source())
        if not gdal_raster:
            raise QgsProcessingException('Unvalid raster layer!')
        
        self.gdal_raster = gdal_raster
        self.geotransform = gdal_raster.GetGeoTransform()

    def get_tiles(self):
        ''' Return list of Tile objects'''
        return self.tiles_list    
  
    def geo_to_pixel(self, x_min, x_max, y_min, y_max):
        """
        Convert a QgsRectangle geographic extent to pixel coordinates.
        """
        # Obtain geotransformation parameters:
        x_origin, pixel_width, _, y_origin, _, pixel_height = self.geotransform

        # Convert geographic to pixel coordinates
        xoff = round((x_min - x_origin) / pixel_width)
        yoff = round((y_max - y_origin) / pixel_height)  # GDAL Y-axis inversion
        xend = round((x_max - x_origin) / pixel_width)
        yend = round((y_min - y_origin) / pixel_height)

        # Calculate width and height in pixels
        width = xend - xoff
        height = yend - yoff
        
        # Adjust offsets and dimensions to ensure they stay within raster bounds
        if xoff < 0:
            width += xoff  # Reduce width by the amount xoff is negative
            xoff = 0
        if yoff < 0:
            height += yoff  # Reduce height by the amount yoff is negative
            yoff = 0
        if xoff + width > self.raster_columns:
            width = self.raster_columns - xoff
        if yoff + height >  self.raster_rows:
            height =  self.raster_rows - yoff
            
        
        # Ensure width and height are non-negative
        width = max(0, width)
        height = max(0, height)

        xend = xoff + width
        yend = yoff + height

        return xoff, yoff, xend, yend
    
    def define_multiples_tiles_pixel(self):
        """
        Generate a list of tiles to process, including a padding region around
        the actual tile. Tiles are defined based on raster pixel coordinates.
        """
        # Define tiles borders:
        if self.raster_columns < self.tile_heigth and self.raster_rows < self.tile_width:
            raise QgsProcessingException("tile_size larger than orthomosaic")
        
        # Print message
        print('Defining tiles borders.')

        # Get the number of rows and columns of tiles based on pixel dimensions
        n_width = np.ceil(self.raster_columns / (self.tile_width * (1 - self.overlap))).astype(int)
        n_height = np.ceil(self.raster_rows / (self.tile_heigth * (1 - self.overlap))).astype(int)

        print('N height and width: ', n_height, n_width)
        # Calculate step size in terms of pixels (not geographic units)
        step_height_pixels = self.tile_heigth * (1 - self.overlap)  # Pixel step for height
        step_width_pixels = self.tile_width * (1 - self.overlap)    # Pixel step for width

        tiles = []

        # Create Tiles object:
        cont = 0
        for r in range(n_height + 1):
            for c in range(n_width + 1):
                # Compute the top-left corner of the tile in pixel coordinates
                tile_r = r * step_height_pixels
                tile_c = c * step_width_pixels
                
                # Define the geographic extent of the tile based on pixel coordinates
                tile_min_x = self.extent.xMinimum() + (tile_c * self.raster_layer.rasterUnitsPerPixelX())
                tile_max_x = tile_min_x + (self.tile_width * self.raster_layer.rasterUnitsPerPixelX())
                tile_min_y = self.extent.yMinimum() + (tile_r * self.raster_layer.rasterUnitsPerPixelY())
                tile_max_y = tile_min_y + (self.tile_heigth * self.raster_layer.rasterUnitsPerPixelY())
                extension_geo = QgsRectangle(tile_min_x, tile_min_y, tile_max_x, tile_max_y, normalize=False)
                
                # Convert geographic rectangle to pixel coordinates
                xoff, yoff, xend, yend = self.geo_to_pixel(tile_min_x, tile_max_x, tile_min_y, tile_max_y)
                extension_pixel = QgsRectangle(xoff, yoff, xend, yend)

                #print(f'Tile number {cont} = {rectangle_pixel[0]}:{rectangle_pixel[0] + rectangle_pixel[2]}, {rectangle_pixel[1]}:{rectangle_pixel[1] + rectangle_pixel[3]}')
                cont += 1
                tiles.append(Tile(extension_geo, extension_pixel, [r, c], self.tile_heigth, self.tile_width, 
                                self.resolution, self.crs, self.left, self.top, self.n_bands))

        # Define processing range of Tile taking into account the overlap:
        no_r = np.max([t.tile_position[0] for t in tiles])
        no_c = np.max([t.tile_position[1] for t in tiles])

        half_overlap_c = (self.tile_width - step_width_pixels) / 2
        half_overlap_r = (self.tile_heigth - step_height_pixels) / 2

        for tile_number, tile in enumerate(tiles):
            tile.tile_number = tile_number
            tile.processing_range = [[half_overlap_r, self.tile_heigth - half_overlap_r],
                                    [half_overlap_c, self.tile_width - half_overlap_c]]

            # Adjust for edges
            if tile.tile_position[0] == 0:
                tile.processing_range[0][0] = 0
            if tile.tile_position[0] == no_r:
                tile.processing_range[0][1] = self.tile_heigth
            if tile.tile_position[1] == 0:
                tile.processing_range[1][0] = 0
            if tile.tile_position[1] == no_c:
                tile.processing_range[1][1] = self.tile_width

        self.tiles_list = tiles
        print('Number of tiles: ', len(self.tiles_list))

    def extract_array_from_tile(self):
        print('Converting tiles to np array GDAL test.')
        num_tiles = len(self.tiles_list)
        cont = 0
        for tile in self.tiles_list:
            #print('Converting tile ', tile.tile_number)
            # worker = TileWorker(self.gdal_raster, tile, num_tiles)
            
            # worker.signals.finished.connect(self.on_tile_finished)
            # self.thread_pool.start(worker)
            tile.read_array_from_tile(self.gdal_raster)
            #tile.read_array_from_tile_test(self.gdal_raster)

        #self.thread_pool.waitForDone()  #  Wait for threads to complete before moving forward.
    
    def save_tiles(self):
        '''
        This function iterate over the tile list using SaveTileWorker for multithreading computing.
        '''
        num_tiles = len(self.tiles_list)
        if  self.output_dir is not None:
            print('Saving tiles images.')
            for tile in self.tiles_list:
                worker = SaveTileWorker(self.output_dir, tile, num_tiles)
                worker.signals.finished.connect(self.on_tile_finished)
                self.thread_pool.start(worker)
                #tile.save_tile(self.output_dir)
            self.thread_pool.waitForDone()  #  Wait for threads to complete before moving forward.


    def on_tile_finished(self):
        # Function to output thread finis message
        print("Tile processing finished.")
        # TODO: Handle clean up if needed
    
    def on_tile_finished_array(self):
        # Function to output thread finis message
        print("Read raster band.")
        # TODO: Handle clean up if needed 


    def get_distance_raster(self):
        '''
        This function iterates over the tiles list and appends the distance images to a single array, 
        to later plug it into the output raster layer band.
        '''
        print('Stitching tiles to generate output raster.')
         # Get the output raster's band and prepare an empty array
        #band = self.output_raster_layer.GetRasterBand(1)
        #stitching_array = np.zeros((band.YSize, band.XSize), dtype=np.uint8)  #GDAL have inverted axes x and y 

        # n_width = np.ceil(self.raster_columns / (self.tile_width * (1 - self.overlap))).astype(int)
        # n_height = np.ceil(self.raster_rows / (self.tile_heigth * (1 - self.overlap))).astype(int)
        # output_width = n_width*self.tile_width
        # output_height = n_height*self.tile_heigth
        stitching_array = np.zeros((self.raster_rows, self.raster_columns), dtype=np.uint8)  #GDAL have inverted axes x and y 
        #stitching_array = np.zeros((output_width, output_height), dtype=np.uint8)  #GDAL have inverted axes x and y 

        for tile in self.tiles_list:
            if tile.distance_img is not None:
                img = np.squeeze(tile.distance_img)

                
                # Extract the rectangle coordinates in pixel space
                rect = tile.rectangle_pixel  # QgsRectangle
                x_min, y_min = int(rect.xMinimum()), int(rect.yMinimum())
                x_max, y_max = int(rect.xMaximum()), int(rect.yMaximum())

                # Ensure the coordinates do not exceed the raster size
                x_max = min(x_max, self.raster_columns)  # Limit x_max to raster width
                y_max = min(y_max, self.raster_rows)    # Limit y_max to raster height

                # Trim the image if it exceeds the raster dimensions
                cropped_img = img[:y_max - y_min, :x_max - x_min]

                # Place the distance image in the appropriate section of the stitching_array
                
                #try:
                stitching_array[y_min:y_max, x_min:x_max] = cropped_img #img[:y_max - y_min,:x_max - x_min] #tile.distance_img[:y_max - y_min, :x_max - x_min]
                print('Distance _ img shape :', cropped_img.shape)
                print(f'To save into {y_max - y_min}, {x_max-x_min}' )
                print('Sucess tile ', tile.tile_number)
                print('')
                #except:
                    # #stitching_array[y_min:y_max, x_min:x_max] = img
                    # print('Distance _ img shape :', cropped_img.shape)
                    # print(f'To save into {y_max - y_min}, {x_max-x_min}' )
                    # print('FAIL in tile ', tile.tile_number)
                    # print('')

        # Write the joined array into the raster band
        # band.SetNoDataValue(0)  # Set NoData value if needed
        # band.WriteArray(stitching_array)

        # # Build pyramids (overviews) for the raster
        # pyramid_levels = [2, 4, 8, 16, 32, 64, 128]  # Define the resolution levels for pyramids
        # gdal.SetConfigOption("COMPRESS_OVERVIEW", "LZW")  # Optional: Compression for overviews
        # self.output_raster_layer.BuildOverviews("AVERAGE", pyramid_levels)

        # band.FlushCache()  # Save the changes to the raster

        # # Convert the in-memory raster to a QgsRasterLayer
        # output_raster_name= 'distance_' + self.raster_layer.name()   # Temporary identifier
        # output_raster_layer = QgsRasterLayer(self.output_raster_layer.GetDescription(), output_raster_name, "gdal")

        # if not output_raster_layer.isValid():
        #     raise RuntimeError("Failed to create QgsRasterLayer from in-memory raster.")
        
        # #print('Ensure pyramid creaded: ', output_raster_layer.GetOverviewCount())
        # # Add the new raster layer to the QGIS workspace
        # QgsProject.instance().addMapLayer(output_raster_layer)

        return stitching_array

class Tile:
    def __init__(self, rectangle, rectangle_pixel, position, height, width, resolution, crs, left, top, n_bands):
        # Data for the tile
        self.size = (height, width)             # Tile size
        self.rectangle = rectangle              # QgsRectangle object - geographical region
        self.rectangle_pixel = rectangle_pixel  # QgsRectangle object - pixel region over raster layer

        self.tile_position = position # Can be removed 
        self.ulc = [rectangle.yMinimum(), rectangle.xMaximum()]
        self.lrc = (rectangle.yMinimum() + height, rectangle.xMaximum() + width)
        self.processing_range = [[0, 0], [0, 0]]    # Can be removed

        self.n_bands = n_bands # Number of band in raster layer
        self.resolution = resolution
        self.crs = crs
        self.left = left
        self.top = top
        self.ulc_global = [
                self.top - (self.ulc[0] * self.resolution[0]), 
                self.left + (self.ulc[1] * self.resolution[1])]
        self.transform = Affine.translation(
            self.ulc_global[1] + self.resolution[0] / 2,
            self.ulc_global[0] - self.resolution[0] / 2) * \
            Affine.scale(self.resolution[0], -self.resolution[0])

        self.tile_number = None

        self.img = None
        self.distance_img = None

    def read_tile(self):
        return self.img 

    def save_tile(self, output_tile_location):
        if  output_tile_location is not None:
            
            name_mahal_results = f'{ output_tile_location }/Tile{ self.tile_number:04d}.tiff'
            img_to_save = self.img
            channels = img_to_save.shape[0]
            
            new_dataset = rasterio.open(name_mahal_results,
                                        'w',
                                        driver='GTiff',
                                        res=self.resolution,
                                        height=self.size[0],
                                        width=self.size[1],
                                        count=channels,
                                        dtype=img_to_save.dtype,
                                        crs=self.crs,
                                        transform=self.transform)
            new_dataset.write(img_to_save)
            new_dataset.close()    
  
        
    def read_array_from_tile(self, raster_gdal):

        height, width = self.size

        xoff, yoff = int(self.rectangle_pixel.xMinimum()), int(self.rectangle_pixel.yMinimum())
        tile_width, tile_height = int(self.rectangle_pixel.width()), int(self.rectangle_pixel.height())
        
        # Init array:
        self.img = np.empty([self.n_bands, height, width], dtype = np.uint8)

        for band in range(1, self.n_bands + 1):
            data = raster_gdal.GetRasterBand(band).ReadAsArray(xoff, yoff, tile_width, tile_height)
            if data is None:
                raise RuntimeError(f"Failed to read band {band}.")
            
            self.img[band - 1, :data.shape[0], :data.shape[1]] = data
       


class TileWorker(QRunnable):
    '''
        This class create a worker for Qgs Multithreading.
        It receives information from the MultiTilesManager and specific Tile and
        invoke the function to extract specific tile region from raster_array
    '''
    def __init__(self, gdal_raster, tile, n_tiles):
        super().__init__()
        self.gdal_raster = gdal_raster
        self.tile = tile
        self.n_tiles = n_tiles
        self.process_tile_func = self.tile.read_array_from_tile
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        # Call function to process each tile
        #print(f"Processing tile {self.tile.tile_number+1} out of {self.n_tiles}")
        self.process_tile_func(self.gdal_raster)
        #print(f"Finished processing tile {self.tile.tile_number+1}")
        #self.signals.result.emit(result)
        self.signals.finished.emit()

class SaveTileWorker(QRunnable):
    '''
        This class create a worker for Qgs Multithreading.
        It receives information from the MultiTilesManager and specific Tile and
        invoke the function to extract specific tile region from raster_array
    '''
    def __init__(self, output_dir, tile, n_tiles):
        super().__init__()
        self.output_dir = output_dir
        self.tile = tile
        self.n_tiles = n_tiles
        self.process_tile_func = self.tile.save_tile
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        # Call function to process each tile
        #print(f"Saving tile {self.tile.tile_number+1} out of {self.n_tiles}")
        self.process_tile_func(self.output_dir)
        #print(f"Finished saving tile {self.tile.tile_number+1}")
        #self.signals.result.emit(result)
        self.signals.finished.emit()

# Define worker signals
class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)