# AgroTool Color Segmenter Plugin

## Description:
Precision agriculture application. This plug-in segments the raster layer based on a color distribution calculated from a shape file or a cropped image over the raster layer. (In development)

## Installation Instructions (only tested in Windows!):
Follow these steps to load and activate the plugin in QGIS:

### 0. Install PyQt and Qt Designer:
- **Ubuntu**:
  ```bash
  sudo apt-get update
  sudo apt-get install python3-pyqt5 pyqt5-dev-tools qttools5-dev-tools
  ```
- **Windows**:
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
- **Windows**:
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


- **Ubuntu**:
- In Ubuntu, you do not need a `.bat` file. Instead, open a terminal and navigate to the plugin directory where the `resources.qrc` file is located.
- Run the following command to compile the resources:
  ```bash
  pyrcc5 -o resources.py resources.qrc
  ```

### 4. Access the Plugin Manager
- Open a new instance of QGIS.
- In QGIS, go to **Plugins > Manage and Install Plugins...**.
- Look for the plugin named **"AgroTool Color Segmenter"** in the list of available plugins.
- Click **Install Plugin** or **Enable Plugin**.

### 5. Use the Plugin
- After activation, look for the **AgroTool Color Segmenter** icon in the toolbar. The icon will display the SDU logo.
- Click on the icon to open the plugin's GUI.

For questions or support, please contact aqu@mmmi.sdu.dk.
