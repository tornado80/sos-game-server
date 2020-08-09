from PySide2.QtCore import QObject, Signal
from sos.core.database_manager import DatabaseManager

class DatabaseModel(QObject, DatabaseManager):
    def __init__(self):
        QObject.__init__(self)
        DatabaseManager.__init__(self)
