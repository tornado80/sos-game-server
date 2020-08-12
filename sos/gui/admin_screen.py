from PySide2.QtWidgets import QWidget
from PySide2.QtCore import Signal
from sos.gui.admin_screen_ui import Ui_AdminScreen
from sos.core.game_server import GameServer

class AdminScreen(QWidget, Ui_AdminScreen):
    signoutRequested = Signal()
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.signoutButton.clicked.connect(self.handle_signout)
        self.startServerButton.clicked.connect(self.handle_start_server)
        self.stopServerButton.clicked.connect(self.handle_stop_server)
    
    def refresh_form(self):
        self.serverStatusLabel.setText("")
        self.stopServerButton.setEnabled(False)
        self.startServerButton.setEnabled(True)
        self.serverAddressLineEdit.setEnabled(True)

    def handle_start_server(self):
        host = self.serverAddressLineEdit.text().split(":")[0].replace("-", "")
        port = int(self.serverAddressLineEdit.text().split(":")[1].replace("-", ""))
        self.startServerButton.setEnabled(False)
        self.stopServerButton.setEnabled(True)
        self.serverAddressLineEdit.setEnabled(False)
        self.game_server = GameServer(self.db_model, host, port)
        self.game_server.start()
        self.serverStatusLabel.setText("Running")
        
    def handle_stop_server(self):
        self.startServerButton.setEnabled(True)
        self.stopServerButton.setEnabled(False)
        self.serverAddressLineEdit.setEnabled(True)
        self.serverStatusLabel.setText("Stopped")
        self.game_server.stop()

    def handle_signout(self):
        self.signoutRequested.emit()
        self.handle_stop_server()