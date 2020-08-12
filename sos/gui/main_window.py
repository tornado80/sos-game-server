from PySide2.QtWidgets import QMainWindow
from sos.gui.main_window_ui import Ui_MainWindow

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, db_model):
        super().__init__()
        self.setupUi(self)
        self.db_model = db_model
        self.loginScreen.db_model = db_model
        self.loginScreen.loginSuccessful.connect(self.navigate_to_admin_screen)
        self.adminScreen.db_model = db_model
        self.adminScreen.signoutRequested.connect(self.navigate_to_login_screen)
        self.admin_session_id = None

    def navigate_to_login_screen(self):
        self.admin_session_id = None
        self.stackedWidget.setCurrentWidget(self.loginScreen)

    def navigate_to_admin_screen(self, session_id):
        self.admin_session_id = session_id
        self.stackedWidget.setCurrentWidget(self.adminScreen)
        self.adminScreen.refresh_form()