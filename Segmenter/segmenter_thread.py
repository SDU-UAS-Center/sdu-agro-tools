import os
import numpy as np
import rasterio
from PyQt5.QtCore import QRunnable, pyqtSignal, QObject, QThreadPool, QEventLoop,  QMutex, QSemaphore
import copy


def process_tile_test(tile_img, colormodel):
        #tile_img=tile.read_tile()   # Change here
        assert isinstance(tile_img, np.ndarray), f"tile_img no es un array numpy: {type(tile_img)}"
        assert tile_img.size > 0, "tile_img está vacío, lo que podría causar errores en la conversión."

        is_empty =  np.max(tile_img[0, :, :]) == np.min(tile_img[0, :, :])
        if is_empty:
            print("EMPTY TILE")
            return None
        else:
            print(f'Processing tile')
            distance_image = colormodel.calculate_distance(tile_img)
            print(f'Distance calculated')
            alpha = 1
            scaled_img=alpha*distance_image
            scaled_img = np.minimum(scaled_img, 255)
            print(f'Scaled done')
            distance = scaled_img.astype(np.uint8)

            return distance    


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
            #print(f'Processing tile {self.tile.tile_number}')
            result = self.func(self.tile_image, self.colormodel)  # Run the task
            #print(f'Finish tile {self.tile.tile_number} with result shape {result.shape}')
            self.signals.result.emit(result)  # Emit result to the main thread
            self.signals.finished.emit()

        except Exception as e:
            self.signals.error.emit(str(e))  # Emit error message to the main thread


class ColorBasedSegmenter(QObject):
    progress_signal = pyqtSignal(int)
    all_results_ready = pyqtSignal()

    def __init__(self, colormodel, param, task, thread_pool):
        super().__init__()

        self.task = task
        self.thread_pool = thread_pool

        self.mutex = QMutex()
        self.completed_tasks = 0

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


    
    def is_image_empty(self, image):
        """Helper function for deciding if an image contains no data."""
        assert isinstance(image, np.ndarray), f"tile_img no es un array numpy: {type(image)}"
        assert image.size > 0, "tile_img está vacío, lo que podría causar errores en la conversión."

        return np.max(image[0, :, :]) == np.min(image[0, :, :])
    
    def apply_colormodel_single_tile(self, tile):
        result = self.process_tile(tile)
        if isinstance(result, np.ndarray):
            tile.distance_img = result
            print(f"Result received: {tile.tile_number} with shape {tile.distance_img.shape}")

            self.save_distance_image(result, tile)

    def apply_colormodel_multi_tiles(self, tiles_list):
        for i, tile in enumerate(tiles_list):
            # Check if the task has been cancelled
            if self.task.isCanceled():
                return False  # Exit early if canceled
            
            result = self.process_tile(tile)

            
            if isinstance(result, np.ndarray):
                tile.distance_img = result
                print(f"Result received: {tile.tile_number} with shape {tile.distance_img.shape}")

                self.save_distance_image(result, tile)
            
            # Emit progress:
            progress = int(40 + (80-40)*((i+1)/len(tiles_list)))
            self.progress_signal.emit(progress)


    def process_tile(self, tile_img, colormodel):
        #tile_img=tile.read_tile()   # Change here
        if self.is_image_empty(tile_img):
            print("EMPTY TILE")
            return None
        else:
            print(f'Processing tile')
            distance_image = colormodel.calculate_distance(tile_img)
            print(f'Distance calculated')
            distance = self.convertScaleAbs(distance_image, self.output_scale_factor)
            print(f'Scaled done')
            distance = distance.astype(np.uint8)

            return distance    


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
    
    def process_tile_develop(self, tile_img, colormodel):
 
        print('Processing')
        return np.random.rand(1, tile_img.shape[1], tile_img.shape[2])
        
    def apply_colormodel_multi_tiles_thread(self, tiles_list):
        n_tiles = len(tiles_list)
        # Submit tasks to the thread pool
        for tile in tiles_list:
            
            current_tile = tile
            tile_image = np.copy(tile.read_tile())
            local_colormodel = copy.deepcopy(self.colormodel)
            worker = MultiTilesWorker(process_tile_test, tile_image, local_colormodel)
            #worker.signals.result.connect(partial(self.handle_result, current_tile))
            #worker.signals.result.connect(lambda result, t=tile: self.handle_result(t, result))
            worker.signals.result.connect(lambda result, t=tile, n=n_tiles: self.handle_result(t, result, n))


            #worker.signals.result.connect(lambda tile, result: self.handle_result(tile, result))
            worker.signals.error.connect(self.handle_error)
            worker.signals.finished.connect(lambda _, t=current_tile: print(f"Thread for tile {t.tile_number} finished"))
            self.thread_pool.start(worker)

        # Wait for all tasks to complete, but don't block the GUI
        loop = QEventLoop()
        self.all_results_ready.connect(loop.quit)  # When signal emitted, loop finish
        loop.exec_()  # Stop main script execution
    
    def handle_result(self, tile, result, n_tiles):
        self.mutex.lock()
        print('Saving result')
        # Handle results and store them in the object's attributes
        self.completed_tasks += 1

        if result is not None:
            tile.distance_img = result
            print(f"Result received: {tile.tile_number} with shape {tile.distance_img.shape}")

            self.save_distance_image(result, tile)
        # TODO: Save tiles

        # Check if all tasks are done
        if self.completed_tasks == n_tiles:
            self.all_results_ready.emit()   # Release execution of main script
            #self.semaphore.release()
        self.mutex.unlock()

    def handle_error(self, error_message):
        self.all_results_ready.emit()
        # TODO: Change to QErrorMessage
        print(f"Error occurred: {error_message}")