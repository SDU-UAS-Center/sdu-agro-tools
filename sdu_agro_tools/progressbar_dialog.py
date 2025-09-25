import os

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox
from PyQt5.QtCore import pyqtSignal, QObject
from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ColorSegmenter_progressbar.ui'))


class GUI_signals(QObject):
    
    cancel_singal = pyqtSignal()

    def __init__(self):
        super().__init__()

class AgroTool_ColorSegmenterProgressBar(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(AgroTool_ColorSegmenterProgressBar, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        self.progressBar.setValue(0)

       
        self.singnal = GUI_signals()

        # Handle task cancellation
        self.CancelButton.clicked.connect(self.on_cancel)

        
    
    def on_cancel(self):
        # Call the cancellation method of your task.
        self.singnal.cancel_singal.emit()
        print('Button pressed')
        self.close()  # Close the progress dialog