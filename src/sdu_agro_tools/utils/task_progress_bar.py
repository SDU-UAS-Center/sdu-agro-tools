import os

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import QObject, pyqtSignal

DIALOG_CLASS = uic.loadUiType(os.path.join(os.path.dirname(__file__), "task_progress_bar.ui"))[0]


class GUI_signals(QObject):  # type: ignore[misc]
    cancel_signal = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()


class TaskProgressBarDialog(QtWidgets.QDialog, DIALOG_CLASS):  # type: ignore[misc, valid-type]
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
