.. _references:

Reference
============================================

Color Distance Calculator
---------------------------------------------------

The core library used by this plugin is **Color Distance Calculator (CDC)**.

CDC is an open-source tool that enables the calculation of color-based distance to a reference color for each pixel in a georeferenced orthomosaic.
We encourage users to explore its full capabilities in the official `CDC documentation <https://henrikmidtiby.github.io/CDC/>`_.

Used Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This plugin leverages several key components from the CDC library:

- ``Color distribution calculator``: See the `Color Model Reference Manual <https://henrikmidtiby.github.io/CDC/reference/CDC.color_models.html#module-CDC.color_models>`_.
- ``Orthomosaic tiler``: See the `Orthomosaic Tiler Reference Manual <https://henrikmidtiby.github.io/CDC/reference/CDC.orthomosaic_tiler.html#module-CDC.orthomosaic_tiler>`_.
- ``Color-based distance calculator``: See the `Color-Based Distance Calculation Reference Manual <https://henrikmidtiby.github.io/CDC/reference/CDC.tiled_color_based_distance.html#module-CDC.tiled_color_based_distance>`_.

References
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- CDC Package - Official documentation: `<https://henrikmidtiby.github.io/CDC/>`_



.. _concurrent-futures:

Multi-Thread Task Execution
---------------------------------------------------
The Python standard library module **concurrent.futures** is used to manage background task execution using threads or processes.
In the context of this plugin, it is primarily used to improve performance by allowing **parallel calculation of multiple tiles color distance**.

Although ``concurrent.futures`` is design to avoid block the main computing thread, in the QGIS framework it is required to utilize QgsTask in other to avoid blocking the QGIS user interfaces.
Therefore, the multi-thread computation with ``concurrent.futures`` is implemented within a QgsTask. Find more about this in :ref:`Background Execution with QgsTask <background-execution>`.


Used Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- ``ThreadPoolExecutor``: Enables launching multiple threads for concurrent task execution.
- ``Future``: An object representing an operation that will complete in the future.

References
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Official documentation: `<https://docs.python.org/3/library/concurrent.futures.html>`_.


.. _background-execution:

Background Execution with QgsTask
--------------------------------------

Heavy, long-running geoprocessing tasks can freeze the QGIS interface if executed directly in the main (GUI) thread.
To prevent this, QGIS provides the `QgsTask <https://qgis.org/pyqgis/3.40/core/QgsTask.html>`_ class—a lightweight wrapper for running tasks in a background thread.
This enables asynchronous processing, keeping the QGIS interface responsive during execution.

Tasks implemented with ``QgsTask`` can be integrated with Python’s ``concurrent.futures`` module to:

- **Offload heavy work** (e.g., computing color distances between tiles) to background threads.
- **Avoid blocking the GUI**, allowing users to interact with QGIS while the task runs.
- **Report progress and messages** via the QGIS task manager.
- **Cancel tasks** cleanly, without needing low-level Qt threading APIs.



Minimal Example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import concurrent.futures
   from qgis.core import (
       QgsTask, QgsApplication, QgsMessageLog, Qgis
   )

   # Dummy function to simulate processing a tile
   def process_tile(tile_class):
       # Simulated processing logic
       pass

   class MultiThread_Tiles(QgsTask):
       def __init__(self, description, tiles, max_threads=4):
           super().__init__(description)
           self.tiles = tiles
           self.max_threads = max_threads

       def run(self):
           # Heavy processing in background thread
           with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_threads) as executor:
               for _ in executor.map(process_tile, self.tiles):
                   pass
           return True

       def finished(self, result):
           # Runs in the main thread after task completion
           if result:
               QgsMessageLog.logMessage("Task completed successfully.", level=Qgis.Info)
           else:
               QgsMessageLog.logMessage("Task was canceled or failed.", level=Qgis.Warning)

   # Example usage
   tiles_to_process = range(100)  # Dummy tile list
   task = MultiThread_Tiles("Example background task", tiles=tiles_to_process)
   QgsApplication.instance().taskManager().addTask(task)


References
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* QgsTask  – PyQGIS API Reference: `<https://qgis.org/pyqgis/3.40/core/QgsTask.html>`_.
* Tasks – PyQGIS Developer Cookbook: `<https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/tasks.html>`_.
* QgsTaskManager - PyQGIS API Reference: `<https://qgis.org/pyqgis/3.40/core/QgsTaskManager.html>`_.
