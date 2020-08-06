import sys
from sos.core.database_manager import DatabaseManager
from sos.core.game_server import GameServer

def test_game_server():
    db_manager = DatabaseManager()
    server = GameServer(db_manager, "127.0.0.1", 12345)
    server.start()
    server.join()

if __name__ == "__main__":
    test_game_server()