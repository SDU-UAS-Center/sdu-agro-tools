
Installation 
============================================


**QGIS AgrooTool Color Segmenter** operates as a plugin within the `QGIS framework <https://qgis.org/>`_.

There are two methods available for installation:

Automatic installation – *Not yet available*
---------------------------------------------------------------------

The plugin can be installable directly through the QGIS graphical user interface using the tool :guilabel:`Manage and Install Plugins...`.

1. Open the menu: ``Plugins ► Manage and Install Plugins...``
2. Select :guilabel:`Not installed` from the left menu.
3. Search for **AgrooTool Color Segmenter**.
4. Click on :guilabel:`Install Plugin`.

QGIS will copy the plugin into the local plugin directory and automatically install the required Python dependencies.

This is the most common and recommended installation method for general users.

.. warning::

    This method is currently not available until the plugin is published in the QGIs official plugin repository. Please use the manual method described below.




Manual installation
-------------------------------

.. |three-dot-icon| raw:: html

    <img src="_static/icon/icon_threedots.png" style="height:1.2em; vertical-align:middle;" alt="Three dots icon">

Alternatively, the plugin can be installed manually by accessing its source code.

**A. Installation from ZIP**

1. Download the ZIP archive containing the source code from `this link <https://gitlab.sdu.dk/hde/sdu-agriculture-qgis-plugin/-/archive/main/sdu-agriculture-qgis-plugin-main.zip>`_.
2. Open the menu: ``Plugins ► Manage and Install Plugins...``
3. Select :guilabel:`Install from ZIP` from the left-hand menu.
4. Click the |three-dot-icon| button to browse for the downloaded ZIP file, then click :guilabel:`Install Plugin`.

QGIS will unzip the contents into the local plugin folder and register the plugin.

**B. Clone Git Repository**

For advanced users, it is also possible to install the plugin by cloning the repository directly into the QGIS local plugin directory.

1. Locate the local plugin folder. This can be done via:

   ``Settings ► User Profiles ► Open Active Profile Folder``

   A file browser window will open. Then navigate to:

   ``python ► plugins``

   The plugin folder path typically looks like:

   ``.../QGIS/QGIS3/profiles/default/python/plugins``

2. For **Windows** user open the **OSGeo4W Shell** or **Command Prompt**. For **maxOS / Linux** simply open a terminal. Then run the following commands:

   .. code-block:: shell

      cd path/to/local/plugin/repository
      git clone git@gitlab.sdu.dk:hde/sdu-agriculture-qgis-plugin.git


3. Restart QGIS and enable the plugin via the Plugin Manager:

   ``Plugins ► Manage and Install Plugins...``


Dependencies
------------------

The plugin depends on the following Python packages:

- ``CDC`` (Color Distance Calculator)
- ``numpy``
- ``rasterio``


QGIS will attempt to install these automatically via the ``requires`` field in the plugin’s ``metadata.txt``.

If the plugin does not load or throws import errors, you can **install the dependencies manually**:

**Manual installation via pip:**

.. code-block:: shell

   pip install numpy rasterio CDC

Or, on Windows using OSGeo4W Shell:

.. code-block:: shell

   python-qgis -m pip install numpy rasterio CDC
  

Troubleshooting
-------------------------------

- If the **plugin does not appear in the Plugin Manager** after installation:

  - Ensure the plugin was extracted or cloned into the correct path.
  - Check that the plugin folder contains a ``metadata.txt`` file and the main plugin code.

- To check for **Python-related errors**:

  - Open ``View ► Panels ► Log Messages Panel`` in QGIS and review the **Python** tab.

- If the **plugin is visible but does not activate**:

  - Restart QGIS to ensure all dependencies are loaded properly.
  - Verify your environment has access to the required Python libraries listed above.