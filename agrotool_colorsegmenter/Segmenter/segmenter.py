import os
import numpy as np
import rasterio


class ColorBasedSegmenter():
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
        for tile in tiles_list:
            result = self.process_tile(tile)
            if isinstance(result, np.ndarray):
                tile.distance_img = result
                print(f"Result received: {tile.tile_number} with shape {tile.distance_img.shape}")

                self.save_distance_image(result, tile)

    
    def process_tile(self, tile):
        tile_img=tile.read_tile()   # Change here
        if self.is_image_empty(tile_img):
            print("EMPTY TILE")
            return None
        else:
            distance_image = self.colormodel.calculate_distance(tile_img)
            distance = self.convertScaleAbs(distance_image, self.output_scale_factor)
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