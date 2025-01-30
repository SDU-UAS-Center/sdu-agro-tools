import os
import time
import numpy as np
import rasterio
import multiprocessing
from PyQt5.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject, pyqtSlot, QThread
from qgis.core import QgsMessageLog
from tqdm import tqdm

import time
# import gc

# gc.set_debug(gc.DEBUG_LEAK)
def convertScaleAbs(img,alpha):
    scaled_img=alpha*img
    for i, value in np.ndenumerate(scaled_img):
        scaled_img[i]=min(value,255)
    return scaled_img


class ColorBasedSegmenter:
    def __init__(self, thread_pool, colormodel, param):

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

        # Scale factor for output'
        self.output_scale_factor = param.scale_factor

        # QGIS multiprocessing
        thread_pool_ = QThreadPool()  # Create pool of Thread
        thread_pool_.setMaxThreadCount(os.cpu_count())  # Set number of cpu count
        self.thread_pool = thread_pool_

    def save_distance_image_main_thread(self, distance_image, tile):
        # Save the processed distance image in the main thread
        print(f"Result: {distance_image}, Tile: {tile.tile_number}")
        tile.distance_img = distance_image  # Safe to modify here
        self.save_distance_image(distance_image, tile)
        self.n_active_workers -= 1

    def apply_colormodel_to_tiles_test2(self, tile_list):
        # Set the thread pool size to a reasonable limit
        max_threads = QThread.idealThreadCount()  # Get the number of CPU cores
        self.thread_pool.setMaxThreadCount(max_threads)

        print("Initializing Color Segmentation")
        n_tiles = len(tile_list)
        self.workers = []  # Keep references to prevent garbage collection
        self.n_active_workers = 0
        
        for tile in tile_list:
            tile_img = tile.read_tile()  # Read tile data in the main thread
            print(tile_img.shape)
            if self.is_image_empty(tile_img):
                print("EMPTY TILE")
                continue

            # Create worker
            thread = QThread()
            worker = SegmenterWorker_test2(tile, tile_img, n_tiles, self.process_tile_test)
            worker.moveToThread(thread)

            thread.started.connect(worker.run)
            worker.signals.result.connect(lambda result, tile=tile: self.save_distance_image_main_thread(result, tile))
            #worker.signals.result.connect(lambda result, tile: print(f"Result signal received: {result}"))
           
            worker.signals.finished.connect(thread.quit)
            worker.signals.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)

            #self.workers.append(worker)
            try:
                thread.start()
            except:
                pass
            self.n_active_workers += 1
            #worker.run()
            
            if self.n_active_workers >= max_threads:
                print('Waiting.')
                self.thread_pool.waitForDone()
            # Wait if the thread pool is fully occupied
            # while self.n_active_workers >= max_threads:
            #     print('waiting',end='\r')
            #     time.sleep(0.1)  

            time.sleep(0.5)
            break
            #if cont >= max_threads: break
            # Start the worker in the thread pool
    
    # TODO: Explore QgsTaskManager
            
    def apply_colormodel_to_tiles_test(self, tile_list):
        # Set the thread pool size to a reasonable limit
        max_threads = QThread.idealThreadCount()  # Get the number of CPU cores
        self.thread_pool.setMaxThreadCount(max_threads)

        print("Initializing Color Segmentation")
        n_tiles = len(tile_list)
        self.workers = []  # Keep references to prevent garbage collection
        self.n_active_workers = 0
        
        for tile in tile_list:
            tile_img = tile.read_tile()  # Read tile data in the main thread
            print(tile_img.shape)
            if self.is_image_empty(tile_img):
                print("EMPTY TILE")
                continue

            # Create worker
            worker = SegmenterWorker_test(tile, tile_img, n_tiles, self.process_tile_test)
            #worker.signals.result.connect(lambda result, tile=tile: self.save_distance_image_main_thread(result, tile))
            worker.signals.result.connect(lambda result, tile: print(f"Result signal received"))
            worker.signals.finished.connect(self.on_tile_finished)
            self.workers.append(worker)
            self.thread_pool.start(worker)
            #worker.run()
            
            if self.thread_pool.activeThreadCount() >= max_threads:
                print('Waiting.')
                self.thread_pool.waitForDone()
            # Wait if the thread pool is fully occupied
            # while self.n_active_workers >= max_threads:
            #     print('waiting',end='\r')
            #     time.sleep(0.1)  

            time.sleep(0.5)
            #if cont >= max_threads: break
            # Start the worker in the thread pool
           

        self.thread_pool.waitForDone()

    def apply_colormodel_to_tiles(self, tile_list):
        
        print('Initilizating Color Segmentation')
        n_tiles = len(tile_list)
        cont = 0
        for tile in tile_list:
            print("Segmenting tile ", tile.tile_number)
            cont += 1
            # if cont > 0: break
            time.sleep(0.1)

            self.process_tile(tile)

        # gc.collect()

        # print("Uncollected objects:", gc.garbage)
    

    def on_tile_finished(self):
        try:
            print("Worker finished successfully.")
        except Exception as e:
            print(f"Error in on_tile_finished: {e}")

    
    def apply_colormodel_to_single_tile(self, tile):
        #self.ensure_parent_directory_exist(self.output_dir)
        start = time.time()
    
        self.process_tile(tile)
        print("Time to run all tiles: ", time.time() - start)     
    

    
    def is_image_empty(self, image):
        """Helper function for deciding if an image contains no data."""
        return np.max(image[0, :, :]) == np.min(image[0, :, :])
    
    # TODO: Delete this function
    def ensure_parent_directory_exist(self, path):
        if not os.path.isdir(path):
            os.makedirs(path)

    def process_tile_test(self, tile, tile_img):
        # Process the tile image in the worker thread
        distance_image = self.colormodel.calculate_distance(tile_img)
        distance = convertScaleAbs(distance_image, alpha=self.output_scale_factor)
        distance = distance.astype(np.uint8) 
        tile.distance_img = distance_image  # Safe to modify here
        self.save_distance_image(distance_image, tile)
        return distance  # Return processed result


    def process_tile(self, tile):
        tile_img=tile.read_tile()   # Change here
        if self.is_image_empty(tile_img):
            print("EMPTY TILE")
            return
        if not self.is_image_empty(tile_img):
            
            distance_image = self.colormodel.calculate_distance(tile_img)
            distance = convertScaleAbs(distance_image,alpha=self.output_scale_factor)
            distance = distance.astype(np.uint8)

            # Save distance image:
            tile.distance_img = distance
            self.save_distance_image(distance, tile)

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

class SegmenterWorker(QRunnable):
    '''
        This class create a worker for Qgs Multithreading.
    '''
    def __init__(self, tile, n_tiles, func):
        super().__init__()
        self.tile = tile
        self.n_tiles = n_tiles
        self.process_tile_func = func
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            # Call function to process each tile
            print(f"Segmenting tile {self.tile.tile_number+1} out of {self.n_tiles}")
            self.process_tile_func(self.tile)
            print(f"Finished segmenting tile {self.tile.tile_number+1}")
            self.signals.result.emit()
            self.signals.finished.emit()
        except Exception as e:
            print(f"Error in worker for tile {self.tile.tile_number}: {e}")
        finally:
            # Ensure cleanup
            pass

class SegmenterWorker_test2(QObject):
    '''
        This class create a worker for Qgs Multithreading.
    '''
    def __init__(self, tile,  tile_img, n_tiles, func):
        super().__init__()
        self.tile = tile
        self.tile_img = tile_img
        self.n_tiles = n_tiles
        self.process_tile_func = func
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            # Call function to process each tile
            print(f"Segmenting tile {self.tile.tile_number+1} out of {self.n_tiles}")
            result = self.process_tile_func(self.tile_img)
            self.signals.result.emit(result)  # Emit the result
        except Exception as e:
            print(f"Error in worker for tile {self.tile.tile_number}: {e}")
        finally:
            # Ensure cleanup
            self.signals.finished.emit()

class SegmenterWorker_test(QRunnable):
    '''
        This class create a worker for Qgs Multithreading.
    '''
    def __init__(self, tile,  tile_img, n_tiles, func):
        super().__init__()
        self.tile = tile
        self.tile_img = tile_img
        self.n_tiles = n_tiles
        self.process_tile_func = func
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            # Call function to process each tile
            print(f"Segmenting tile {self.tile.tile_number+1} out of {self.n_tiles}")
            result = self.process_tile_func(self.tile, self.tile_img)
            self.signals.result.emit(result)  # Emit the result
        except Exception as e:
            print(f"Error in worker for tile {self.tile.tile_number}: {e}")
        finally:
            # Ensure cleanup
            self.signals.finished.emit()

# Define worker signals
class WorkerSignals(QObject):
    finished = pyqtSignal()
    result = pyqtSignal(object)