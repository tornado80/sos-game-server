from threading import Thread, Lock, RLock
import socket
from time import sleep, time
import random
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
    MAX_PLAYER = 20
    def __init__(self, db_manager, game_id):
        super().__init__()
        self.__db_manager = db_manager
        self.__game_id = game_id
        self.__players_connections = {}
        self.__players_address = {}
        self.__players_scores = {}
        self.__players_colors = {}
        self.__players_turn = []
        self.__players_hints = {}
        self.__current_player_turn = None
        self.__generated_colors = []
        self.__online_players = 0
        self.__occupied_cells_number = 0
        self.__last_activity = time()
        self.__has_winner = False
        self._tasks_queue = Queue()
        self.get_game_information()
        self.__game_board = [[[None, None] for i in range(self.__board_size)] for j in range(self.__board_size)]
        self.generate_colors()

    def generate_colors(self):
        i = int(random.random() * 360)
        step = 360 // self.MAX_PLAYER
        for j in range(self.MAX_PLAYER):
            self.__generated_colors.append((i + j * step) % 360)
        random.shuffle(self.__generated_colors)

    def get_game_information(self):
        result = self.__db_manager.get_game_information(self.__game_id)
        self.__player_count = result[0]
        self.__board_size = result[1]
        self.__who_created = result[2]
        self.__who_created_username = result[3]
        self.__max_hint = result[4]

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
            elif response["command"] == "game_runner_my_turn":
                task = {
                    "command" : "player_turn_done_task",
                    "account_id" : account_id,
                    "row" : response["data"]["row"],
                    "column" : response["data"]["column"],
                    "letter" : response["data"]["letter"]
                }
                self._tasks_queue.enqueue(task)
            elif response["command"] == "game_runner_hint":
                task = {
                    "command" : "please_help_task",
                    "account_id" : account_id
                }
                self._tasks_queue.enqueue(task)                

    def broadcast_players_status(self):
        response = Packet()
        response["command"] = "game_runner_players_status"
        response["data"] = {
            "scores" : {}, 
            "colors" : {},
            "hints" : {},
            "status" : {}
        }
        for player_account_id, player_connection in self.__players_connections.items():
            player_username = self.__db_manager.get_username_from_account_id(player_account_id)
            response["data"]["colors"][player_username] = self.__players_colors[player_account_id]
            response["data"]["scores"][player_username] = str(self.__players_scores[player_account_id])
            response["data"]["hints"][player_username] = str(self.__players_hints[player_account_id]) + "h"
            if player_connection != None:
                response["data"]["status"][player_username] = "online"
            else:
                response["data"]["status"][player_username] = "offline"
        for player_connection in self.__players_connections.values():
            if player_connection != None:
                response.send(player_connection)

    def broadcast_board_status(self):
        response = Packet()
        response["command"] = "game_runner_board_status"
        response["data"] = {
            "board" : []
        }
        for i in range(self.__board_size):
            response["data"]["board"].append([])
            for j in range(self.__board_size):
                if self.__game_board[i][j][0] != None:
                    response["data"]["board"][i].append([
                            self.__players_colors[self.__game_board[i][j][0]], self.__game_board[i][j][1]
                        ]
                    )
                else:
                    response["data"]["board"][i].append(["silver", ""])
        for player_connection in self.__players_connections.values():
            if player_connection != None:
                response.send(player_connection)

    def broadcast_start_game(self):
        self.__players_turn = list(self.__players_connections.keys())
        random.shuffle(self.__players_turn)
        self.__current_player_turn = 0
        self.broadcast_player_turn()

    def broadcast_player_turn(self):
        account_id = self.__players_turn[self.__current_player_turn]
        player_connection = self.__players_connections[account_id]
        if player_connection == None:
            return
        response = Packet()
        response["command"] = "game_runner_your_turn"
        response.send(player_connection)

    def broadcast_winner(self):
        response = Packet()
        response["command"] = "game_runner_winner_announced"
        sorted_scores = sorted(list(self.__players_scores.items()), key=lambda player_score : player_score[1], reverse=True)
        if sorted_scores[0][1] == sorted_scores[1][1]:
            response["draw"] = True
            self.__db_manager.set_game_ended(self.__game_id, None)
        else:
            response["winner"] = self.__db_manager.get_username_from_account_id(sorted_scores[0][0])
            self.__db_manager.update_account_games_and_wins(sorted_scores[0][0], 0, 1)
            self.__db_manager.set_game_ended(self.__game_id, sorted_scores[0][0])
        for player_account_id, player_connection in self.__players_connections.items():
            self.__db_manager.update_account_games_and_wins(player_account_id, 1, 0)
            if player_connection != None:
                response.send(player_connection)
        self.__has_winner = True        

    def check_for_sos_triple(self, account_id, row, column, letter, no_act = False):
        neighbour_cells = [
            (row - 1, column - 1),
            (row - 1, column),
            (row - 1, column + 1),
            (row, column - 1),
            (row, column + 1),
            (row + 1, column - 1),
            (row + 1, column),
            (row + 1, column + 1)
        ]
        second_layer_neighbor_cells = [
            (row - 2, column - 2),
            (row - 2, column),
            (row - 2, column + 2),
            (row, column - 2),
            (row, column + 2),
            (row + 2, column - 2),
            (row + 2, column),
            (row + 2, column + 2)
        ]
        found = False
        counter = 0
        if letter == "S":
            for i in range(8):
                cell = neighbour_cells[i]
                if 0 <= cell[0] < self.__board_size and 0 <= cell[1] < self.__board_size:
                    if self.__game_board[cell[0]][cell[1]][1] == "O":
                        second_layer_cell = second_layer_neighbor_cells[i]
                        if 0 <= second_layer_cell[0] < self.__board_size and 0 <= second_layer_cell[1] < self.__board_size:
                            if self.__game_board[second_layer_cell[0]][second_layer_cell[1]][1] == "S":
                                found = True
                                counter += 1
                                if not no_act:
                                    self.__game_board[second_layer_cell[0]][second_layer_cell[1]][0] = account_id
                                    self.__game_board[cell[0]][cell[1]][0] = account_id
        else: # letter == "O"
            for i in range(4):
                row1 = neighbour_cells[i][0]
                row2 = neighbour_cells[7 - i][0]
                col1 = neighbour_cells[i][1]
                col2 = neighbour_cells[7 - i][1]
                if 0 <= row1 < self.__board_size and 0 <= col1 < self.__board_size and 0 <= col2 < self.__board_size and 0 <= row2 < self.__board_size:
                    if self.__game_board[row1][col1][1] == self.__game_board[row2][col2][1] == "S":
                        found = True
                        counter += 1
                        if not no_act:
                            self.__game_board[row1][col1][0] = account_id
                            self.__game_board[row2][col2][0] = account_id
        return found, counter

    def find_good_place(self):
        for i in range(self.__board_size):
            for j in range(self.__board_size):
                if self.__game_board[i][j][0] is None:
                    found, _ = self.check_for_sos_triple(None, i, j, "S", no_act = True)
                    if found:
                        return i, j, "S"
                    found, _ = self.check_for_sos_triple(None, i, j, "O", no_act = True)
                    if found:
                        return i, j, "O"
        return None

    def run(self):
        while True:
            if not self._tasks_queue.is_empty():
                task = self._tasks_queue.dequeue()
                if task["command"] == "new_player_connection_task":
                    account_id = task["account_id"]
                    sock = task["socket"]
                    client_address = task["client_address"]
                    if self.__has_winner:
                        response = Packet()
                        response["command"] = "game_runner_new_player_banned"
                        response["data"] = {
                            "error" : "Game has been finished."
                        } 
                        response.send(sock)                        
                    elif account_id in self.__players_connections and self.__players_connections[account_id] != None:
                        response = Packet()
                        response["command"] = "game_runner_new_player_banned"
                        response["data"] = {
                            "error" : "You have joined the game with another session."
                        } 
                        response.send(sock)
                    else:
                        self.__online_players += 1
                        self.__players_connections[account_id] = sock
                        self.__players_address[account_id] = client_address
                        if account_id not in self.__players_scores:
                            self.__players_scores[account_id] = 0
                        if account_id not in self.__players_hints:
                            self.__players_hints[account_id] = 0                            
                        if account_id not in self.__players_colors:
                            self.__players_colors[account_id] = "hsl({}, 100%, 50%)".format(str(self.__generated_colors[len(self.__players_connections)]))
                        Thread(target=self.player_listener, args=(account_id, sock)).start()
                        response = Packet()
                        response["command"] = "game_runner_game_details"
                        response["data"] = {
                            "game_id" : self.__game_id,
                            "board_size" : self.__board_size,
                            "player_count" : self.__player_count,
                            "creator_username" : self.__who_created_username,
                            "color" : self.__players_colors[account_id],
                            "max_hint" : self.__max_hint
                        }
                        response.send(sock)
                        self.broadcast_players_status()
                        self.broadcast_board_status()
                        if self.__current_player_turn != None:
                            if self.__players_turn[self.__current_player_turn] == account_id:
                                self.broadcast_player_turn()
                        else:
                            if len(self.__players_connections) == self.__player_count: # game has not started yet but enough players
                                self.broadcast_start_game()
                elif task["command"] == "disconnect_player_task":
                    account_id = task["account_id"]
                    sock = self.__players_connections[account_id]
                    response = Packet()
                    response["command"] = "game_runner_abort"
                    response.send(sock)
                    self.__players_connections[account_id].close()
                    self.__players_connections[account_id] = None
                    self.broadcast_players_status()
                    self.__online_players -= 1
                    if self.__online_players == 0:
                        self.__last_activity = time()
                elif task["command"] == "player_turn_done_task":
                    account_id = task["account_id"]
                    row = task["row"]
                    column = task["column"]
                    letter = task["letter"]
                    if self.__players_turn[self.__current_player_turn] == account_id:
                        self.__game_board[row][column] = [account_id, letter]
                        self.__db_manager.add_game_log(self.__game_id, account_id, letter, row, column)
                        self.__occupied_cells_number += 1
                        found, count = self.check_for_sos_triple(account_id, row, column, letter)
                        if not found:
                            self.__current_player_turn += 1
                            if self.__current_player_turn == len(self.__players_turn):
                                self.__current_player_turn = 0
                        else:
                            self.__players_scores[account_id] += count
                        self.broadcast_players_status()
                        self.broadcast_board_status()                          
                        if self.__occupied_cells_number == (self.__board_size * self.__board_size):
                            self.broadcast_winner()
                        else:
                            self.broadcast_player_turn()
                elif task["command"] == "please_help_task":
                    account_id = task["account_id"]
                    response = Packet()
                    response["command"] = "game_runner_hint_result"                    
                    if self.__players_turn[self.__current_player_turn] == account_id:
                        if self.__players_hints[account_id] < self.__max_hint:
                            self.__players_hints[account_id] += 1
                            if self.__players_hints[account_id] == self.__max_hint:
                                response["finished"] = True
                            result = self.find_good_place()
                            self.__players_scores[account_id] -= 1
                            if result == None:
                                self.__db_manager.add_game_hint(self.__game_id, account_id, "", 0, 0)
                                response["result"] = "Unfortunately no hint is available."
                            else:
                                self.__db_manager.add_game_hint(self.__game_id, account_id, result[2], result[0] + 1, result[1] + 1)
                                response["result"] = "You can put \"{}\" at row {} and column {} to obtain a SOS.".format(
                                    result[2], str(result[0] + 1), str(result[1] + 1)
                                )
                        else:
                            response["error"] = "You have used all your hints."
                    else:               
                        response["error"] = "It is not your turn."
                    response.send(self.__players_connections[account_id])
                    self.broadcast_players_status()
            else:
                if self.__online_players == 0 and self.__has_winner:
                    return
                if self.__online_players == 0 and (time() - self.__last_activity) > 30:
                    self.__db_manager.set_game_ended(self.__game_id, None)
                    print("Game deleted")
                    return
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
                max_hint = data["max_hint"]
                db_result = self.__db_manager.new_game(session_token, board_size, player_count, is_public, max_hint)
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