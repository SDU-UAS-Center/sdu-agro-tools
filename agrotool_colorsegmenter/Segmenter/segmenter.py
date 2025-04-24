import os
import numpy as np
import rasterio


from PyQt5.QtCore import QRunnable, pyqtSignal, QObject, QThreadPool, QEventLoop,  QMutex, QSemaphore

class ColorBasedSegmenter(QObject):
    """ Class responsible for segmenting images based on a color model. 
        It supports processing individual tiles or multiple tiles in sequence.
    """
    progress_signal = pyqtSignal(int) # Connect to progress bar

    def __init__(self, colormodel, param, task):
        super().__init__()

        self.task = task    # Reference to main task - check cancelation

        # Ensure parent directory exist
        if param.save_tiles_distance:
            output_dir = param.save_tiles_path
            if not os.path.isdir(output_dir):
                os.makedirs(output_dir)
            self.output_dir = output_dir
        else:
            self.output_dir = None
    
        self.colormodel=colormodel  # Color model
        
        # Save as float uint8
        self.convert = param.convert_uint8
        self.output_scale_factor = param.scale_factor   # Scale factor for output

    
    def is_image_empty(self, image):
        """Helper function for deciding if an image contains no data."""
        assert isinstance(image, np.ndarray), f"tile_img not a numpy array: {type(image)}"
        assert image.size > 0, "tile_img is empty!"
        return np.max(image[0, :, :]) == np.min(image[0, :, :])
    
    def apply_colormodel_single_tile(self, tile):
        """ Applies the color model to a single tile."""
        # Check if the task has been cancelled
        if self.task.isCanceled():
            return False  # Exit early if canceled
        
        result = self.process_tile(tile)
        if isinstance(result, np.ndarray):
            tile.distance_img = result
            #print(f"Result received: {tile.tile_number} with shape {tile.distance_img.shape}")
            self.save_distance_image(result, tile)

    def apply_colormodel_multi_tiles(self, tiles_list):
        """ Applies the color model to a list of tiles sequentially."""
        for i, tile in enumerate(tiles_list):
            # Check if the task has been cancelled
            if self.task.isCanceled():
                return False  # Exit early if canceled
            
            result = self.process_tile(tile)
            if isinstance(result, np.ndarray):
                tile.distance_img = result
                #print(f"Result received: {tile.tile_number} with shape {tile.distance_img.shape}")
                self.save_distance_image(result, tile)
            
            # Emit progress:
            progress = int(40 + (80-40)*((i+1)/len(tiles_list)))
            self.progress_signal.emit(progress)

    
    def process_tile(self, tile):
        """ Processes a single tile by applying the color model and scaling the result."""
        tile_img=tile.read_tile()   # Change here
        if self.is_image_empty(tile_img):
            return None
        else:
            distance_image = self.colormodel.calculate_distance(tile_img)
            print("Tile type before ", type(distance_image.dtype))
            # Convert from np.float64 to np.uint8 - save space
            if self.convert:
                distance_image = self.convertScaleAbs(distance_image, self.output_scale_factor)
            #distance = distance.astype(np.uint8)
            print("Tile type after ", type(distance_image.dtype))
            return distance_image    


    def convertScaleAbs(self, img, alpha):
        """ Scales an image using a given factor while ensuring pixel values remain within valid range."""
        scaled_img=alpha*img
        scaled_img = np.minimum(scaled_img, 255) # NOTE: Vectorized operation, modification
        scaled_img = scaled_img.astype(np.uint8)
        return scaled_img
    
    def save_distance_image(self, img, tile):
        """ Saves the processed distance image as a TIFF file if saving is enabled."""
        if  self.output_dir is not None:
            name_mahal_results = f'{ self.output_dir }/distance_tiles{ tile.tile_number:04d}.tiff'
            img_to_save = img
            channels = img_to_save.shape[0]
            new_dataset = rasterio.open(name_mahal_results,
                                        'w',
                                        driver='GTiff',
                                        res=tile.resolution,
                                        height=tile.size[0],
                                        width=tile.size[1],
                                        count=channels,
                                        dtype=img_to_save.dtype,
                                        crs=tile.crs,
                                        transform=tile.transform)
            new_dataset.write(img_to_save)
            new_dataset.close()
            print("Data saved in: ", name_mahal_results)