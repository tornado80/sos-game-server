from threading import Thread
import socket
from concurrent.futures import ThreadPoolExecutor
from sos.utils.protocol import Packet
from sos.core.database_manager import DatabaseManager

class ClientTask:
    def __init__(self, db_manager, connection_sock, address):
        self.__sock = connection_sock
        self.__client_host = address[0]
        self.__client_port = address[1]
        self.__db_manager = db_manager
    
    def __call__(self):
        print("Connected from", self.__client_host, self.__client_port)
        request = Packet.recv(self.__sock)
        command = request["commad"]
        data = request["data"]
        if command == "login_request":
            username = data["username"]
            password = data["password"]
            db_result = self.__db_manager.login(username, password)
            response = Packet()
            response["command"] = "login_response"
            if not isinstance(db_result, Exception):
                response["data"] = {
                    "session_id" : db_result
                }
            else:
                response["data"] = {
                    "error" : str(db_result)
                }
            response.send(self.__sock)

class GameServer(Thread):
    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 12346
    def __init__(self, db_manager, host = None, port = None):
        super().__init__()
        self.__server_host = host if host else GameServer.DEFAULT_HOST
        self.__server_port = port if port else GameServer.DEFAULT_PORT
        self.__db_manager = db_manager
        self.__sock = None
        self.__executor = None

    def run(self):
        self.__sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__sock.bind((self.__server_host, self.__server_port))
        self.__sock.listen()
        self.__executor = ThreadPoolExecutor()
        while True:
            ct = ClientTask(self.__db_manager, *self.__sock.accept())
            self.__executor.submit(ct)