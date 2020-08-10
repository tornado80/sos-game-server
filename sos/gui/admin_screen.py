from PySide2.QtWidgets import QWidget
from sos.gui.admin_screen_ui import Ui_AdminScreen

class AdminScreen(QWidget, Ui_AdminScreen):
    def __init__(self):
        super().__init__()
        self.setupUi(self)