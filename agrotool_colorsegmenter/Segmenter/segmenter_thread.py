from PyQt5.QtCore import QRunnable, pyqtSignal, QObject, QThreadPool, QEventLoop,  QMutex, QSemaphore
import os
import numpy as np
import rasterio

import copy
from functools import partial

class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)  # Optional signal to report errors back to main thread
    result = pyqtSignal(np.ndarray) # Signal to send processed tile result back to main thread

    def __init__(self):
        super().__init__()
       

class MultiTilesWorker(QRunnable):
    

    def __init__(self, func, tile_image, colormodel):
        super().__init__()
        self.func = func
        self.tile_image = tile_image
        self.colormodel = colormodel
        self.signals = WorkerSignals()

    def run(self):
        try:
            #tile, result = self.func(self.tile)  # Run the task
            #self.signals.result.emit(tile, result)  # Emit result to the main thread
            result = self.func(self.tile_image, self.colormodel)  # Run the task
            self.signals.result.emit(result)  # Emit result to the main thread
            self.signals.finished.emit()

            del self.tile_image
            del self.colormodel

        except Exception as e:
            self.signals.error.emit(str(e))  # Emit error message to the main thread



class ColorBasedSegmenter(QObject):
    all_results_ready = pyqtSignal() # Handle end of execution

    def __init__(self, colormodel, param):
        super().__init__()

        # Ensure parent directory exist
        if param.save_tiles_distance:
            output_dir = param.save_tiles_path
            if not os.path.isdir(output_dir):
                os.makedirs(output_dir)
            self.output_dir = output_dir
        else:
            self.output_dir = None

        # Color model
        self.colormodel=colormodel

        # Scale factor for output
        self.output_scale_factor = param.scale_factor

        # Threads control
        self.results = []  # Attribute to store processed results
        self.completed_tasks = 0  # To track completed tasks
        self.mutex = QMutex()

        # self.thread_pool = QThreadPool.globalInstance()
        # self.thread_pool.setMaxThreadCount(4)  # Max concurrent threads

        self.semaphore = QSemaphore(0)


    def handle_result(self, tile, result):
        self.mutex.lock()
        # Handle results and store them in the object's attributes
        self.completed_tasks += 1

        if not np.all(result==0):
            tile.distance_img = result
            print(f"Result received: {tile.tile_number} with shape {tile.distance_img.shape}")

        # TODO: Save tiles

        # Check if all tasks are done
        # if self.completed_tasks == len(self.tiles_list):
        #     #self.all_results_ready.emit()   # Release execution of main script
        #     self.semaphore.release()
        self.mutex.unlock()

    def handle_error(self, error_message):
        # TODO: Change to QErrorMessage
        print(f"Error occurred: {error_message}")

    
    def is_image_empty(self, image):
        """Helper function for deciding if an image contains no data."""
        assert isinstance(image, np.ndarray), f"tile_img no es un array numpy: {type(image)}"
        assert image.size > 0, "tile_img está vacío, lo que podría causar errores en la conversión."

        return np.max(image[0, :, :]) == np.min(image[0, :, :])
    

    def apply_colormodel_multi_tiles(self, tiles_list):

        max_worker = 4
        active_threads = 0
        # Start processing using QThreadPool
        thread_pool = QThreadPool()
        thread_pool.setMaxThreadCount(max_worker)  # Set the number of threads based on CPU

       
        # Submit tasks to the thread pool
        for tile in tiles_list:
            #print(f"Tile ID before worker: {id(tile)}")  # Verificar ID antes de pasar al thread
            tile_image = np.copy(tile.read_tile())
            # Create local instance of color model - save multithreading
            local_colormodel = copy.deepcopy(self.colormodel)
            current_tile = tile
    
            worker = MultiTilesWorker(self.process_tile_development, tile_image, local_colormodel)
            worker.signals.result.connect(partial(self.handle_result, tile))
            #worker.signals.result.connect(lambda tile, result: self.handle_result(tile, result))
            worker.signals.error.connect(self.handle_error)
            worker.signals.finished.connect(lambda _, t=current_tile: print(f"Thread for tile {t.tile_number} finished"))
            thread_pool.start(worker)
            #active_threads += 1

            # cont+=1
            # if active_threads > 4: 
            #     thread_pool.waitForDone()
            #     active_threads = 0
        # Wait for all tasks to complete, but don't block the GUI
        thread_pool.waitForDone()  # This will block the main thread until all tasks are done.
        # Wait for all tasks to complete, but don't block the GUI
        # loop = QEventLoop()
        # self.all_results_ready.connect(loop.quit)  # When signal emitted, loop finish
        # loop.exec_()  # Stop main script execution

        # Wait until all worker threads are finished
        #self.semaphore.acquire()  # Blocks execution until `semaphore.release()` is called



        
        #return self.results
    
    def apply_colormodel_multi_tiles_naive(self):

        # Submit tasks to the thread pool
        for tile in self.tiles_list:
            result = self.process_tile(tile)
            if result != None:
                tile.distance_img = result
                print(f"Result received: {tile.tile_number} with shape {tile.distance_img.shape}")

            # TODO: Save tiles
    
    def process_tile(self, tile):
        tile_img=tile.read_tile()   # Change here
        print(f'Aqui en tile {tile.tile_number}')
        if self.is_image_empty(tile_img):
            print("EMPTY TILE")
            return None
        else:
            distance_image = self.colormodel.calculate_distance(tile_img)
            distance = self.convertScaleAbs(distance_image, self.output_scale_factor)
            distance = distance.astype(np.uint8)

            return distance
            #return np.ones((1, tile_img.shape[1], tile_img.shape[2]))
            # Save distance image:
            # tile.distance_img = distance
            # self.save_distance_image(distance, tile)

    def process_tile_development(self, tile_img, colormodel):
        #tile_img=tile.read_tile()   # Change here
        #print(f'Aqui en tile {tile.tile_number}')
        self.mutex.lock()
        if self.is_image_empty(tile_img):
            print("EMPTY TILE")
            self.mutex.unlock()
            return np.zeros((1, tile_img.shape[1], tile_img.shape[2]))
            
        else:
            
            #distance_image = local_colormodel.calculate_distance_original(tile_img)
            distance_image = self.calculate_distance_local(tile_img, colormodel)
            distance = self.convertScaleAbs(distance_image, self.output_scale_factor)
            distance = distance.astype(np.uint8)
            self.mutex.unlock()
            return distance
    
    def calculate_distance_local(self, tile_img, local_colormodel):
        
        bands_to_use = local_colormodel.bands_to_use
        covariance = local_colormodel.covariance
        average = local_colormodel.average
        inv_cov =  np.linalg.inv(covariance)  
         
        pixels = np.reshape(tile_img[bands_to_use,:,:], (len(bands_to_use),-1)).transpose()
        diff = pixels - average
        modified_dot_product = diff * (diff @ inv_cov)
        distance = np.sum(modified_dot_product, axis=1)
        distance = np.sqrt(distance)

        distance_image = np.reshape(distance, (1,tile_img.shape[1], tile_img.shape[2]))

        return distance_image

    def process_tile_naive_copy(self, tile):
        tile_img=tile.read_tile()   # Change here
        print(f'Aqui en tile {tile.tile_number}')
        if self.is_image_empty(tile_img):
            print("EMPTY TILE")
            return tile, np.empty(tile_img.shape)
        else:

            # Copy variables for save threading:
            bands_to_use = self.colormodel.bands_to_use.copy()  
            covariance = self.colormodel.covariance.copy()  
            average = self.colormodel.average.copy()  
            inv_cov =  np.linalg.inv(covariance)  

            pixels = np.reshape(tile_img[bands_to_use,:,:], (len(bands_to_use),-1)).transpose()
            diff = pixels - average
            modified_dot_product = diff * (diff @ inv_cov)
            distance = np.sum(modified_dot_product, axis=1)
            distance = np.sqrt(distance)

            distance_image = np.reshape(distance, (1,tile_img.shape[1], tile_img.shape[2]))
        
            distance_image = self.colormodel.calculate_distance(tile_img)
            distance = self.convertScaleAbs(distance_image, self.output_scale_factor)
            assert np.all(distance >= 0) and np.all(distance <= 255), "Valores fuera del rango en distancia"
            distance = distance.astype(np.uint8)
            return tile, distance
            # Save distance image:
            # tile.distance_img = distance
            # self.save_distance_image(distance, tile)

    def convertScaleAbs(self, img, alpha):
        scaled_img=alpha*img
        scaled_img = np.minimum(scaled_img, 255) # NOTE: Vectorized operation, modification
        # for i, value in np.ndenumerate(scaled_img):
        #     scaled_img[i]=min(value,255)
        return scaled_img
    
    def save_distance_image(self, img, tile):
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
        else:
            print("not saving images")