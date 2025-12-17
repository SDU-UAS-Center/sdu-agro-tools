# SDU Agro Tools Plugin

## Description

Precision agriculture application. This plug-in segments the raster layer based on a color distribution calculated from a shape file or a cropped image over the raster layer. (In development)

## Installation Instructions Windows

Follow these steps to load and activate the plugin in QGIS:

### 0. Install PyQt and Qt Designer

Download and install the necessary dependencies for PyQt5 and Qt Designer. This is usually done when you install QGIS, but make sure these components are available.

### 1. Locate the QGIS Plugin Directory

- Open QGIS.
- Navigate to **Settings > User Profiles > Open Active Profile Folder**.
- This will open the directory where QGIS stores your active profile and plugins.

### 2. Add the Plugin Folder

- Clone the plugin repository or copy the plugin folder to the `python/plugins` directory found inside the profile folder from Step 1.
- If needed change the name of the folder to 'agrotool_colorsegmenter' to ensure compatibility.
- Make sure to restart QGIS after copying the plugin folder to ensure it is detected.

### 3. Compile the GUI .ui File

- Locate the `compile.bat` file in the plugin directory.
- Open the `compile.bat` file in a text editor and update the paths to match your QGIS installation location. It should look something like this:

  ```bat
  @echo off
  call "C:\Path\To\QGIS\bin\o4w_env.bat"
  call "C:\Path\To\QGIS\bin\qt5_env.bat"
  call "C:\Path\To\QGIS\bin\py3_env.bat"

  @echo on
  pyrcc5 -o resources.py resources.qrc
  ```

Replacing `C:\Path\To\QGIS` with the actual QGIS installation directory on your machine.

- Double-click the `compile.bat` file. This will run the necessary commands to **generate the `resources.py` file** from the `resources.qrc` file, which is required for the plugin to work.

## Installation Instructions Linux

- First make sure QGIS is installed and clone the repository to a directory of your choice.

- Sphinx is needed and must be installed. this is best done in a virtual environment:

```sh
python -m venv venv
source ./venv/bin/activate
pip install sphinx
```

- Check that the QGISDIR variable in the makefile references the correct folder for the QGIS installation. The default linux install directory is used but it may differ depending on the QGIS installation.

- Run make deploy to compile GUI files and copy the needed files into the QGIS plugin directory. With the virtual environment sourced.

```sh
make deploy
```

If updating user interface in Qt Designer running `make compile-ui` will update the corresponding python files which is used to import the dialogs and will give autocomplete i editor.

## Access the Plugin Manager

- Open a new instance of QGIS.
- In QGIS, go to **Plugins > Manage and Install Plugins...**.
- Look for the plugin named **"SDU Agro Tools"** in the list of available plugins.
- Click **Install Plugin** or **Enable Plugin**.
- If this gives an error, it is most likely because of missing python dependencies. This can be solved by installing the QPIP plugin.
  - Install QPIP plugin
  - If a popup does not appear try to disable and enable the **"SDU Agro Tools"** plugin.
  - In the popup allow it to install the needed python dependencies.

## Use the Plugin

- After activation, look for the **SDU Agro Tools** icon in the toolbar. The icon will display the SDU logo.
- Click on the icon to open the plugin's GUI.

For questions or support, please contact aqu@mmmi.sdu.dk.
