from PyQt5.QtCore import QRunnable, pyqtSignal, QObject, QThreadPool, QEventLoop,  QMutex, QWaitCondition
import os
import numpy as np

import copy
from functools import partial

class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)  # Optional signal to report errors back to main thread
    result = pyqtSignal(object, np.ndarray) # Signal to send processed tile result back to main thread

    def __init__(self):
        super().__init__()
       

class MultiTilesWorker(QRunnable):
    

    def __init__(self, func, tile):
        super().__init__()
        self.func = func
        self.tile = tile
        self.signals = WorkerSignals()

    def run(self):
        """Runs the worker in a separate thread."""
        try:
            result = self.func(self.tile)  # Process the tile
            self.signals.result.emit(self.tile, result)  # Emit result (tile, processed data)
        except Exception as e:
            self.signals.error.emit(str(e))  # Emit error message
        finally:
            self.signals.finished.emit(self.tile)  # Notify that this worker has finished



class ColorBasedSegmenter:
    def __init__(self, tiles_list, colormodel, param):
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

        # Tiles list
        self.tiles_list = tiles_list

        # Scale factor for output
        self.output_scale_factor = param.scale_factor

        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(4)  # Max concurrent threads
        self.active_threads = 0
        self.task_queue = list(self.tiles_list)  # Copy the tile list
        self.mutex = QMutex()  # Thread-safe counter
        self.wait_condition = QWaitCondition()  # Allow main thread to wait

        self.results = []  # Store results here
        self.completed_tasks = 0  # Count completed tasks

    def handle_result(self, tile, result):
        self.mutex.lock()
        # Handle results and store them in the object's attributes
        #if not np.all(result==0):
        tile.distance_img = result
        print(f"Result received: {tile.tile_number} with shape {tile.distance_img.shape}")

        self.mutex.unlock()

    def handle_error(self, error_message):
        # TODO: Change to QErrorMessage
        print(f"Error occurred: {error_message}")

    
    def is_image_empty(self, image):
        """Helper function for deciding if an image contains no data."""
        assert isinstance(image, np.ndarray), f"tile_img no es un array numpy: {type(image)}"
        assert image.size > 0, "tile_img está vacío, lo que podría causar errores en la conversión."

        return np.max(image[0, :, :]) == np.min(image[0, :, :])
    

    def apply_colormodel_multi_tiles(self):
        for _ in range(min(4, len(self.task_queue))):  # Start initial batch
            self.start_next_worker()
        
        # Wait for all threads to complete before proceeding
        self.mutex.lock()
        while self.completed_tasks < len(self.tiles_list):
            print(f"Main thread waiting... Completed {self.completed_tasks}/{len(self.tiles_list)}")
            self.wait_condition.wait(self.mutex)
        self.mutex.unlock()

        print("All tiles processed. Proceeding with main thread execution.")

    def start_next_worker(self):
        """Starts the next worker if there are remaining tasks."""
        self.mutex.lock()  # Ensure thread-safe modification of active_threads
        if self.task_queue and self.active_threads < 4:
            tile = self.task_queue.pop(0)  # Get next tile
            worker = MultiTilesWorker(self.process_tile, tile)

            # Handle worker signals
            worker.signals.result.connect(lambda result, tile=tile: self.handle_result(tile, result))
            worker.signals.error.connect(self.handle_error)
            worker.signals.finished.connect(lambda tile=tile: self.on_worker_finished(tile))

            self.active_threads += 1  # Increase active thread count
            self.thread_pool.start(worker)
        self.mutex.unlock()


    def on_worker_finished(self, tile):
        """Called when a worker completes to start a new one if needed."""
        self.mutex.lock()
        self.active_threads -= 1  # Decrease active thread count
        self.completed_tasks += 1
        self.mutex.unlock()

        print(f"Thread for tile {tile.tile_number} finished")


        # Wake up the main thread if all tasks are done
        if self.completed_tasks == len(self.tiles_list):
            self.mutex.lock()
            self.wait_condition.wakeAll()
            self.mutex.unlock()

        # Start next worker if there are more tasks
        self.start_next_worker()

    
    def process_tile(self, tile):
        tile_img=tile.read_tile()   # Change here
        print(f'Aqui en tile {tile.tile_number}')
        if self.is_image_empty(tile_img):
            print("EMPTY TILE")
            return np.zeros((1, tile_img.shape[1], tile_img.shape[2]))
        else:
            # Create local instance of color model - save multithreading
            local_colormodel = copy.deepcopy(self.colormodel)
    
            #distance_image = local_colormodel.calculate_distance_original(tile_img)
            # distance_image = self.calculate_distance_local(tile_img, local_colormodel)
            # distance = self.convertScaleAbs(distance_image, self.output_scale_factor)
            # assert np.all(distance >= 0) and np.all(distance <= 255), "Valores fuera del rango en distancia"
            # distance = distance.astype(np.uint8)

            del local_colormodel

            return tile, np.zeros((1, tile_img.shape[1], tile_img.shape[2]))
            #return np.ones((1, tile_img.shape[1], tile_img.shape[2]))
            # Save distance image:
            # tile.distance_img = distance
            # self.save_distance_image(distance, tile)
    
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
        
            #distance_image = self.colormodel.calculate_distance(tile_img)
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