from PyQt5.QtCore import QObject, pyqtSignal
from qgis.PyQt import QtWidgets

from .task_progress_bar_ui import Ui_TaskProgressBarDialog


class GUI_signals(QObject):  # type: ignore[misc]
    cancel_signal = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()


class TaskProgressBarDialog(QtWidgets.QDialog, Ui_TaskProgressBarDialog):  # type: ignore[misc]
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Constructor."""
        super().__init__(parent)
        self.setupUi(self)
        self.progressBar.setValue(0)
        self.signal = GUI_signals()
        self.CancelButton.clicked.connect(self.on_cancel)

    def on_cancel(self) -> None:
        self.signal.cancel_signal.emit()
        self.close()
