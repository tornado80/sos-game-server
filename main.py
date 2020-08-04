from PySide2.QtWidgets import QApplication
import sys
from sos.gui.main_window import MainWindow
from sos.core.game_server import GameServer

class SOSGameServerApp(QApplication):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.main_window = MainWindow()
        self.main_window.show()

app = SOSGameServerApp(sys.argv)
app.exec_()
