from PySide2.QtWidgets import QMainWindow
from sos.gui.main_window_ui import Ui_MainWindow

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, db_model):
        super().__init__()
        self.setupUi(self)
        self.db_model = db_model
