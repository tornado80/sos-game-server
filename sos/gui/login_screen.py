from PySide2.QtWidgets import QWidget
from sos.gui.login_screen_ui import Ui_LoginScreen

class LoginScreen(QWidget, Ui_LoginScreen):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.loginButton.clicked.connect(self.handle_login)

    def handle_login(self):
        print("login button clicked")