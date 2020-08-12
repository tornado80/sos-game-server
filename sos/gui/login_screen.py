from PySide2.QtWidgets import QWidget, QMessageBox
from PySide2.QtCore import Signal
from sos.gui.login_screen_ui import Ui_LoginScreen

class LoginScreen(QWidget, Ui_LoginScreen):
    loginSuccessful = Signal(str)
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.loginButton.clicked.connect(self.handle_login)

    def handle_login(self):
        username = self.usernameLineEdit.text()
        password = self.passwordLineEdit.text()
        if username == "" or password == "":
            QMessageBox.critical(self, "Error", "All fields are essential.")
            return
        db_result = self.db_model.login(username, password, is_admin = True)
        if isinstance(db_result, Exception):
            QMessageBox.critical(self, "Error", str(db_result))
        else:
            self.loginSuccessful.emit(db_result)