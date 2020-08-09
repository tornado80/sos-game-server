from PySide2.QtWidgets import QApplication
import sys
from sos.gui.main_window import MainWindow
from sos.core.game_server import GameServer
from sos.core.database_model import DatabaseModel

class SOSGameServerApp(QApplication):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_model = DatabaseModel()
        self.main_window = MainWindow(self.db_model)
        self.main_window.show()

app = SOSGameServerApp(sys.argv)
app.exec_()
