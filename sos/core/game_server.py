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
        request = Packet.recv(self.__sock)
        print(request)

class GameServer(Thread):
    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = "12345"
    def __init__(self, db_manager, host = None, port = None):
        self.__server_host = host if host else GameServer.DEFAULT_HOST
        self.__server_port = port if port else GameServer.DEFAULT_PORT
        self.__db_manager = db_manager
        self.__sock = None
        self.__executor = None

    def run(self):
        try:
            self.__sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.__sock.bind((self.__server_host, self.__server_port))
            self.__sock.listen()
        except Exception as err:
            print("Can not start server due to following error:\n\t", err)
            return
        self.__executor = ThreadPoolExecutor()
        while True:
            ct = ClientTask(self.__db_manager, *self.__sock.accept())
            self.__executor.submit(ct)

if __name__ == "__main__":
    import sys
    options = sys.argv
    if "host" not in options or "port" not in options:
        print("Please provide host and port in format \"host = x.x.x.x and port = y\".")
        exit()
    else:
        try:
            host = options[options.index("host") + 2]
            port = int(options[options.index("port") + 2])
            db_manager = DatabaseManager()
            server = GameServer(db_manager, host, port)
            server.start()
            server.join()
        except IndexError:
            print("Host or port is missing. Please provide host and port in format \"host = x.x.x.x and port = y\".")
        except Exception as e:
            print(e)
        finally:
            exit()