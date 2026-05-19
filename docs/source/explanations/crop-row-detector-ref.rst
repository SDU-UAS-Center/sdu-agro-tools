Crop Row Detector Reference
===========================

This is a reference manual for Crop Row Detector, where all parameters and options are explained in more details.

Input and Thresholds
--------------------

Crop Row Detector needs one input, which is a gray scale raster layer where the crops have values closes to zero.
Such gray scale raster can be obtained from running CDC, see :doc:`cdc-ref`.

Optionally the original orthomosaic can be supplied under ``Input Orthomosaic`` if one wants to save a raster layer with crop rows draw on.

In ``Threshold to apply to Color Distance Image`` a threshold value need to be supplied which will convert the input gray scale into black and white in order to segment the crops from the background.

In ``Threshold to apply to crop row vegetation`` a threshold value can be supplied which is applied to the amount of vegetation "around" a crop point for it to be considered crop or a gap in the crop row. This is only applied to the output ``Save output crop points`` and all crop point regardless of vegetation value is saved in ``Save crop information``. See :ref:`crd-output for more information on the different output formats.

Crop Settings
-------------

.. role:: raw-html(raw)
    :format: html

If the direction of the crop rows is know and uniform across the entire orthomosaic, limiting the crop row angle can help speed up the crop row detecting. This can also be use full if only crop rows of a certain direction is desired but the orthomosaic contain multiple directions.

By setting `M̀in Angle of Crop Rows`` and ``Max Angle of Crop Rows`` one can limit crop row to be within these degrees. The degrees are measured as on a compass with 0:raw-html:`&deg; being North, 90:raw-html:`&deg; being East, 180:raw-html:`&deg; being South and 270:raw-html:`&deg; being West. Since a crop row pointing east is also pointing west only degrees between 0:raw-html:`&deg; and 180:raw-html:`&deg; is used.

In ``ANgular division`` the number that each degree is split into can be supplied. A higher number will be a better resolution for crop row angle but at the cost of computation time and resources.

In ``Distance between Crop Rows`` the distance of the crop rows can be supplied in centimeters. This will be dependent on the crop and sowing machine used.

Tile Processing
---------------

The plugin improves performance by dividing the input raster layer into **multiple tiles**, which are processed in parallel using multithreading. This means that the color distance calculation is distributed across several **threads**, with each thread handling a different tile of the image at the same time. This parallel execution significantly reduces processing time, especially for large orthomosaics.

For in-depth information on multithreaded execution, refer to the :ref:`notes-concurrent-futures`.

You can configure the **tile size** to control how the raster is split.

.. _cdc-tile-size:

Tile Dimensions
~~~~~~~~~~~~~~~

You can customize the **width** and **height** of the tiles into which the input raster layer is divided. These dimensions determine how the raster is split and directly impact the **number of tiles** generated, which in turn can affect the **total computation time**.

.. |arrows-icon| raw:: html

    <img src="../_static/icon/icon_arrows.png" style="height:1.2em; vertical-align:middle;" alt="arrow icon">

To adjust the tile size, use the |arrows-icon| in the :guilabel:`Tiles width` and :guilabel:`Tiles height` fields, or enter the desired values manually in the corresponding text boxes.
The default tile size is **512 × 512 pixels**.

The tiles can also be overlapping by setting :guilabel:`Tile overlap` which will increase the size of the tile used for processing. This can be beneficial for detecting crop rows on the edge of the tiles. Increasing tile overlap will significantly increase computational resources and time.

Each tile is processed with it own crop row direction so decreasing the tile size can help finding the correct crop row direction if the crop row direction changes a lot across the orthomosaic.

.. _crd-output:

Output
------

The main output is saved as csv files and a location in which to save the files can be chosen with :guilabel:`Save Crop information`. The output consist of the following files:

* points_in_rows.csv
* points_in_rows_wkt.csv
* row_information.csv
* row_information_global.csv
* row_information_global_wkt.csv

describe content for csv files.

Optionally the orthomosaic with crop rows draw on can be saved with :guilabel:`Save output orthomosaic`. Default saves it as a temporary file open in QGIS that is discarded when QGIS is closed.

Optionally crop points can be saved with :guilabel:`Save output crop points` which default saves a temporary QGIS vector layer which is discarded when QGIS is closed.

Optionally crop rows can be saved with :guilabel:`Save output crop rows` which default saves a temporary QGIS vector layer which is discarded when QGIS is closed.
