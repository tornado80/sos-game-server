from threading import Thread
import socket
from time import sleep
from concurrent.futures import ThreadPoolExecutor
from sos.utils.protocol import Packet
from sos.core.database_manager import DatabaseManager

class ClientTask:
    def __init__(self, db_manager, game_server, connection_sock, address):
        self.__sock = connection_sock
        self.__client_host = address[0]
        self.__client_port = address[1]
        self.__game_server = game_server
        self.__db_manager = db_manager
    
    def __call__(self):
        print("Connected from", self.__client_host, self.__client_port)
        request = Packet.recv(self.__sock)
        command = request["command"]
        data = request["data"]
        if self.__game_server.is_stopped():
            response = Packet()
            response["command"] = command.replace("request", "response")
            response["data"] = {
                "error" : "Server has been stopped."
            }
            response.send(self.__sock)
        elif self.__game_server.is_paused():
            response = Packet()
            response["command"] = command.replace("request", "response")
            response["data"] = {
                "error" : "Server has been paused."
            }
            response.send(self.__sock)
        else:
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
            elif command == "signup_request":
                username = data["username"]
                password = data["password"]
                first_name = data["firstname"]
                last_name = data["lastname"]
                db_result = self.__db_manager.add_account(username, password, first_name, last_name)
                response = Packet()
                response["command"] = "signup_response"
                if not isinstance(db_result, Exception):
                    response["data"] = {
                        "ok" : "done"
                    }
                else:
                    response["data"] = {
                        "error" : str(db_result)
                    }
                response.send(self.__sock)
            elif command == "signout_request":
                session_token = data["session_id"]
                db_result = self.__db_manager.logout(session_token)
                response = Packet()
                response["command"] = "signout_response"
                if not isinstance(db_result, Exception):
                    response["data"] = {
                        "ok" : "done"
                    }
                else:
                    response["data"] = {
                        "error" : str(db_result)
                    }
                response.send(self.__sock)
            elif command == "get_account_request":
                session_token = data["session_id"]
                db_result = self.__db_manager.get_account(session_token)
                response = Packet()
                response["command"] = "get_account_response"
                if not isinstance(db_result, Exception):
                    response["data"] = db_result
                    response["data"]["ok"] = "done"
                else:
                    response["data"] = {
                        "error" : str(db_result)
                    }
                response.send(self.__sock)
            elif command == "edit_account_request":
                session_token = data["session_id"]
                current_password = data["current_password"]
                username = data["username"]
                password = data["password"]
                first_name = data["first_name"]
                last_name = data["last_name"]
                db_result = self.__db_manager.edit_account(session_token, current_password, username, password, first_name, last_name)
                response = Packet()
                response["command"] = "edit_account_response"
                if not isinstance(db_result, Exception):
                    response["data"] = {
                        "ok" : "done"
                    }
                else:
                    response["data"] = {
                        "error" : str(db_result)
                    }
                response.send(self.__sock)
            elif command == "edit_profile_request":
                session_token = data["session_id"]
                current_password = data["current_password"]
                first_name = data["first_name"]
                last_name = data["last_name"]
                db_result = self.__db_manager.edit_profile(session_token, current_password, first_name, last_name)
                response = Packet()
                response["command"] = "edit_profile_response"
                if not isinstance(db_result, Exception):
                    response["data"] = {
                        "ok" : "done"
                    }
                else:
                    response["data"] = {
                        "error" : str(db_result)
                    }
                response.send(self.__sock)
            elif command == "edit_username_request":
                session_token = data["session_id"]
                current_password = data["current_password"]
                username = data["username"]
                db_result = self.__db_manager.change_username(session_token, current_password, username)
                response = Packet()
                response["command"] = "edit_username_response"
                if not isinstance(db_result, Exception):
                    response["data"] = {
                        "ok" : "done"
                    }
                else:
                    response["data"] = {
                        "error" : str(db_result)
                    }
                response.send(self.__sock)
            elif command == "edit_password_request":
                session_token = data["session_id"]
                current_password = data["current_password"]
                new_password = data["new_password"]
                db_result = self.__db_manager.change_password(session_token, current_password, new_password)
                response = Packet()
                response["command"] = "edit_password_response"
                if not isinstance(db_result, Exception):
                    response["data"] = {
                        "ok" : "done"
                    }
                else:
                    response["data"] = {
                        "error" : str(db_result)
                    }
                response.send(self.__sock)            
            elif command == "remove_account_request":
                session_token = data["session_id"]
                current_password = data["current_password"]
                db_result = self.__db_manager.remove_account(session_token, current_password)
                response = Packet()
                response["command"] = "remove_account_response"
                if not isinstance(db_result, Exception):
                    response["data"] = {
                        "ok" : "done"
                    }
                else:
                    response["data"] = {
                        "error" : str(db_result)
                    }
                response.send(self.__sock)
        self.__sock.close()

class GameServer(Thread):
    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 12345
    def __init__(self, db_manager, host = None, port = None):
        super().__init__()
        self.__server_host = host if host else GameServer.DEFAULT_HOST
        self.__server_port = port if port else GameServer.DEFAULT_PORT
        self.__db_manager = db_manager
        self.__sock = None
        self.__executor = None
        self.__is_paused = False
        self.__is_stopped = False

    def run(self):
        self.__sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__sock.bind((self.__server_host, self.__server_port))
        self.__sock.listen()
        self.__executor = ThreadPoolExecutor()
        while True:
            if not self.__is_paused and not self.__is_paused:
                ct = ClientTask(self.__db_manager, self, *self.__sock.accept())
                self.__executor.submit(ct)
            else:
                if self.__is_stopped:
                    self.__sock.close()
                    # shutdown game servers
                    # self.__executor.shutdown()
                    # break loop
                else:
                    sleep(0.2)

    def pause(self):
        self.__is_paused = True
        self.make_sure_exiting_accept_block()

    def make_sure_exiting_accept_block(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock: # this is to ensure returning from accept block
                sock.connect((self.__server_host, self.__server_port))
                sock.close()
        except:
            pass

    def is_paused(self):
        return self.__is_paused

    def is_stopped(self):
        return self.__is_stopped

    def stop(self):
        self.__is_stopped = True
        self.make_sure_exiting_accept_block()