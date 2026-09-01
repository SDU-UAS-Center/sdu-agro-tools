Installation
============

**SDU Agro Tools** is a plugin within `QGIS <https://qgis.org/>`_. It can be installed with the QGIS plugin Manager.

Below is alternative ways to install the latest release or from source code.

.. note::

    On some systems (Ubuntu 24, flatpak and maybe more) the automatic installation of dependencies may fail by installing python packages not needed as the system python packages are to be used. QPIP will install numpy and scipy no matter what options are selected in QPIP. If this is the case it solution is to delete the installed packages manually. This can be done by opening the dependencies folder in QGIS:

    ``Plugins ► QPIP ► Show library folder in explorer``

    Find the following folders and delete them:

    * numpy
    * numpy.libs
    * nmumpy-2.5.2.dist-info
    * scipy
    * scipy.libs
    * scipy-1.18.1.dist-info

    nmumpy-2.5.2.dist-info and scipy-1.18.1.dist-info might have a different number depending on the installed version.

    Now close and open QGIS again and the plugin should work.

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
