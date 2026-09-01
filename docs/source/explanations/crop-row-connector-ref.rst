Crop Row Connector Reference
============================

This is a reference manual for Crop Row Connector, where all parameters and options are explained in more details.


.. figure:: ../_static/tutorial/crop-row-connector/dialog.png

Inputs
------

Crop Row Connector needs two inputs, which is two vector layers, one with the crop rows and one with crop points.
Such vector layers can be obtained from running crop row detector, see :doc:`crop-row-detector-ref`.

Row Settings
------------

.. role:: raw-html(raw)
    :format: html

These setting can be used to change how crop rows are connected. `Angle tolerance` is the difference i direction between two rows in which it is below before they are considered to be connected. `Distance tolerance` is the distance between two rows to consider them for connected.

It is a good idea to keep the `Distance tolerance` below the distance between 2 parallel crop rows.

Vegetation settings
-------------------

These settings determine the healthy og unhealthy segments of the rows. `Vegetation threshold` determines when a crop point is considered healthy/unhealthy and is applied to the vegetation attribute of the input crop points.

`Max segment length` determines the maximum length of each segments and `Min unhealthy segment length` determines the minimum length of unhealthy segments.

Output
------

The main output is two QGIS vector layers, one with all the healthy crop segments and one with the unhealthy crop segments. As default these layers are saved as temporary files in memory and are discarded when QGIS is closed unless saved.
