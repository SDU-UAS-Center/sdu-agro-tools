Installation
============

**SDU Agro Tools** is a plugin within `QGIS <https://qgis.org/>`_.

Install from ZIP
----------------

Download the latest release from `github releases <https://github.com/SDU-UAS-Center/sdu-agro-tools/releases>`_ as a ZIP file.

In QGIS:

    ``Plugins ► Manage and Install Plugins``

    In the plugin window select:

    ``Install from ZIP``

    Select the downloaded ZIP file and click:

    ``Install Plugin``

When installing it will install another plugin called **qpip** that will manage python dependencies.

Qpip will open a new window and ask for installing python dependencies. Clicking **OK** will install the necessary dependencies.

Install from source code
------------------------

Either download the source code or git clone the `repository <https://github.com/SDU-UAS-Center/sdu-agro-tools>`_.

Locate the local plugin folder. This can be done via:

   ``Settings ► User Profiles ► Open Active Profile Folder``

   A file browser window will open. Then navigate to:

   ``python ► plugins``

   The plugin folder path typically looks like:

   ``.../QGIS/QGIS3/profiles/default/python/plugins``

Change the **QGISDIR** variable in **/src/sdu_agro_tools/Makefile** to reflect your local plugin folder.

run ``uv run make deploy`` to install plugin to local plugin folder.

In QGIS:

    ``Plugins ► Manage and Install Plugins``

    In the plugin window select:

    ``Installed``

    Find **SDU Agro Tools** in the list and enable.

When installing it will install another plugin called **qpip** that will manage python dependencies.

Qpip will open a new window and ask for installing python dependencies. Clicking **OK** will automatically install the necessary dependencies.
