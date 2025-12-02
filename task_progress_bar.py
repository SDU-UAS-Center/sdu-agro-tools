from PyQt5.QtCore import QObject, pyqtSignal
from qgis.PyQt import QtWidgets

from .task_progress_bar_ui import Ui_TaskProgressBarDialog


class GUI_signals(QObject):
    cancel_signal = pyqtSignal()

    def __init__(self):
        super().__init__()


class TaskProgressBarDialog(QtWidgets.QDialog, Ui_TaskProgressBarDialog):
    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(parent)
        self.setupUi(self)
        self.progressBar.setValue(0)
        self.signal = GUI_signals()
        # Handle task cancellation
        self.CancelButton.clicked.connect(self.on_cancel)

    def on_cancel(self):
        # Call the cancellation method of your task.
        self.signal.cancel_signal.emit()
        print("Button pressed")
        self.close()  # Close the progress dialog
