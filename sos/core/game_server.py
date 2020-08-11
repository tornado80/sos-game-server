from threading import Thread, Lock, RLock
import socket
from time import sleep
from concurrent.futures import ThreadPoolExecutor
from sos.utils.protocol import Packet
from sos.core.database_manager import DatabaseManager

class QueueNode:
    def __init__(self, data):
        self.next = None
        self.data = data

class Queue:
    def __init__(self):
        self.head = None
        self.tail = None
        self.lock = Lock()
    
    def is_empty(self):
        if self.head is None and self.tail is None:
            return True
        return False

    def enqueue(self, data):
        self.lock.acquire()
        node = QueueNode(data)
        if self.is_empty():            
            self.head = self.tail = node
        else:
            self.tail.next = node
            self.tail = node
        self.lock.release()
        return True

    def dequeue(self):
        self.lock.acquire()
        if self.head is not None:
            node = self.head
            self.head = node.next
            if self.head is None:
                self.tail = None
            self.lock.release()
            return node.data
        else:
            self.lock.release()
            return None        

class GameRunner(Thread):
    def __init__(self, db_manager, game_id):
        super().__init__()
        self.__db_manager = db_manager
        self.__game_id = game_id
        self.__players_connections = {}
        self.__players_address = {}
        self.__players_scores = {}
        self._tasks_queue = Queue()
        self.get_game_information()

    def get_game_information(self):
        result = self.__db_manager.get_game_information(self.__game_id)
        self.__player_count = result[0]
        self.__board_size = result[1]
        self.__who_created = result[2]
        self.__who_created_username = result[3]        

    def player_listener(self, account_id, sock):
        while True:
            response = Packet.recv(sock)
            if response["command"] == "game_runner_disconnect":
                task = {
                    "command" : "disconnect_player_task",
                    "account_id" : account_id
                }
                self._tasks_queue.enqueue(task)
                return

    def broadcast_players_status(self):
        response = Packet()
        response["command"] = "game_runner_players_status"
        response["data"] = {
            "players" : {}
        }
        for player_account_id, player_connection in self.__players_connections.items():
            player_username = self.__db_manager.get_username_from_account_id(player_account_id)
            if player_connection != None:
                response["data"]["players"][player_username] = str(self.__players_scores[player_account_id])
            else:
                response["data"]["players"][player_username] = "offline"
        for player_connection in self.__players_connections.values():
            if player_connection != None:
                response.send(player_connection)

    def broadcast_board_status(self):
        pass

    def run(self):
        while True:
            if not self._tasks_queue.is_empty():
                task = self._tasks_queue.dequeue()
                if task["command"] == "new_player_connection_task":
                    account_id = task["account_id"]
                    sock = task["socket"]
                    client_address = task["client_address"]
                    if account_id in self.__players_connections and self.__players_connections[account_id] != None:
                        response = Packet()
                        response["command"] = "game_runner_new_player_banned"
                        response["data"] = {
                            "error" : "You have joined the game with another session."
                        } 
                        response.send(sock)
                    else:
                        self.__players_connections[account_id] = sock
                        self.__players_address[account_id] = client_address
                        if account_id not in self.__players_scores:
                            self.__players_scores[account_id] = 0
                        Thread(target=self.player_listener, args=(account_id, sock)).start()
                        response = Packet()
                        response["command"] = "game_runner_game_details"
                        response["data"] = {
                            "game_id" : self.__game_id,
                            "board_size" : self.__board_size,
                            "player_count" : self.__player_count,
                            "creator_username" : self.__who_created_username
                        }
                        response.send(sock)
                        self.broadcast_players_status()
                        self.broadcast_board_status()
                elif task["command"] == "disconnect_player_task":
                    account_id = task["account_id"]
                    sock = self.__players_connections[account_id]
                    response = Packet()
                    response["command"] = "game_runner_abort"
                    response.send(sock)
                    self.__players_connections[account_id].close()
                    self.__players_connections[account_id] = None
                    self.broadcast_players_status()
            else:
                sleep(0.01)

class ClientTask:
    def __init__(self, db_manager, game_server, connection_sock, address):
        self.__sock = connection_sock
        self.__client_host = address[0]
        self.__client_port = address[1]
        self.__client_address = address
        self.__game_server = game_server
        self.__db_manager = db_manager
    
    def __call__(self):
        print("Connected from", self.__client_host, self.__client_port)
        request = Packet.recv(self.__sock)
        command = request["command"]
        data = request["data"]
        long_time_connection = False
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
            elif command == "new_game_request":
                session_token = data["session_id"]
                board_size = data["board_size"]
                player_count = data["player_count"]
                is_public = data["is_public"]
                db_result = self.__db_manager.new_game(session_token, board_size, player_count, is_public)
                if not isinstance(db_result, Exception):
                    game_id = db_result[0]
                    account_id = db_result[1]
                    long_time_connection = True
                    self.__game_server.add_to_runners(game_id)
                    task = {
                        "command" : "new_player_connection_task",
                        "account_id" : account_id,
                        "socket" : self.__sock,
                        "client_address" : self.__client_address
                    }
                    self.__game_server._game_runners[game_id]._tasks_queue.enqueue(task)
                else:
                    response = Packet()
                    response["command"] = "new_game_response"                    
                    response["data"] = {
                        "error" : str(db_result)
                    }
                    response.send(self.__sock)
            elif command == "join_game_request":
                session_token = data["session_id"]
                game_id = data["game_id"]
                creator_username = data["creator_username"]
                db_result = self.__db_manager.join_game(session_token, game_id, creator_username)
                if not isinstance(db_result, Exception):
                    account_id = db_result
                    long_time_connection = True
                    task = {
                        "command" : "new_player_connection_task",
                        "account_id" : account_id,
                        "socket" : self.__sock,
                        "client_address" : self.__client_address
                    }
                    self.__game_server._game_runners[game_id]._tasks_queue.enqueue(task)
                else:
                    response = Packet()
                    response["command"] = "join_game_response"                    
                    response["data"] = {
                        "error" : str(db_result)
                    }
                    response.send(self.__sock)                
        if not long_time_connection:
            self.__sock.close()

class GameServer(Thread):
    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 12345
    def __init__(self, db_manager, host = None, port = None):
        super().__init__()
        self.__server_host = host if host else GameServer.DEFAULT_HOST
        self.__server_port = port if port else GameServer.DEFAULT_PORT
        self.__db_manager = db_manager
        self._game_runners = {}
        self.__sock = None
        self.__executor = None
        self.__is_paused = False
        self.__is_stopped = False

    def add_to_runners(self, game_id):
        runner = GameRunner(self.__db_manager, game_id)
        self._game_runners[game_id] = runner
        runner.start()

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
                    # shutdown game runners
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