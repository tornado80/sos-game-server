from datetime import date
import sqlite3
import hashlib
import datetime
import secrets
import functools
from threading import Lock

class ExistingUsernameError(Exception):
    pass

class WrongUsernamePasswordError(Exception):
    pass

class InvalidSessionTokenError(Exception):
    pass

db_lock = Lock()

def db_transaction(function):
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        try:
            db_lock.acquire()
            return_value = function(*args, **kwargs)
        except Exception as error:
            return error
        else:
            return return_value
        finally:
            db_lock.release()
    return wrapper

class DatabaseManager:
    SQLITE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS Accounts (
        account_id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        rating INTEGER NOT NULL DEFAULT 0 CHECK (rating >= 0),
        number_of_wins INTEGER NOT NULL DEFAULT 0 CHECK (number_of_wins >= 0),
        number_of_games INTEGER NOT NULL DEFAULT 0 CHECK (number_of_games >= 0),
        when_joined TEXT NOT NULL,
        when_deleted TEXT,
        last_login TEXT,
        is_admin INTEGER NOT NULL DEFAULT 0 CHECK (is_admin == 1 OR is_admin == 0),
        is_disabled INTEGER NOT NULL DEFAULT 0 CHECK (is_disabled == 1 OR is_disabled == 0)
    );
    CREATE TABLE IF NOT EXISTS Sessions (
        session_id INTEGER PRIMARY KEY,
        token TEXT NOT NULL,
        when_created TEXT NOT NULL,
        account_id INTEGER NOT NULL,
        FOREIGN KEY (account_id) REFERENCES Accounts (account_id)
    );
    CREATE TABLE IF NOT EXISTS Games (
        game_id INTEGER PRIMARY KEY,
        winner INTEGER,
        player_count INTEGER NOT NULL CHECK (player_count > 0),
        board_size INTEGER NOT NULL CHECK (player_count > 0),
        is_public INTEGER NOT NULL CHECK (is_public == 1 OR is_public == 0),
        when_created TEXT NOT NULL,
        who_created INTEGER NOT NULL,
        FOREIGN KEY (winner) REFERENCES Accounts (account_id),
        FOREIGN KEY (who_created) REFERENCES Accounts (account_id) 
    );
    CREATE TABLE IF NOT EXISTS Players (
        player_id INTEGER PRIMARY KEY,
        game_id INTEGER NOT NULL,
        account_id INTEGER NOT NULL,
        when_joined TEXT NOT NULL,
        FOREIGN KEY (game_id) REFERENCES Games (game_id),
        FOREIGN KEY (account_id) REFERENCES Accounts (account_id)        
    );
    CREATE TABLE IF NOT EXISTS GameLogs (
        gamelog_id INTEGER PRIMARY KEY,
        log_number INTEGER NOT NULL CHECK (log_number > 0),
        row_number INTEGER NOT NULL CHECK (row_number >= 0),
        column_number INTEGER NOT NULL CHECK (column_number >= 0),
        letter TEXT NOT NULL CHECK (letter == 'S' OR letter == 'O'),
        game_id INTEGER NOT NULL,
        account_id INTEGER NOT NULL,
        log_datetime TEXT NOT NULL,
        FOREIGN KEY (game_id) REFERENCES Games (game_id),
        FOREIGN KEY (account_id) REFERENCES Accounts (account_id)
    );
    CREATE TABLE IF NOT EXISTS Actions (
        action_id INTEGER PRIMARY KEY,
        who INTEGER,
        action_datetime TEXT NOT NULL,
        report TEXT NOT NULL,
        FOREIGN KEY (who) REFERENCES Accounts (account_id)
    );    
    """
    def __init__(self, db_path = "db.sqlite3"):
        self.db_path = db_path
        self.setup_connection()

    def setup_connection(self):
        if self.open_connection():
            self.setup_database()

    def open_connection(self):
        try:
            self.db_connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.db_cursor = self.db_connection.cursor()
            return True
        except sqlite3.Error as err:
            self.show_errors_to_user(err)
            return False

    def is_database_valid(self) -> bool:
        try:
            self.db_cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            self.db_connection.commit()
            for tbl in self.db_cursor.fetchall():
                if tbl[0] not in ["Accounts", "Sessions", "Games", "Players", "GameLogs", "Actions"]:
                    return False
            return True
        except sqlite3.Error as err:
            self.show_errors_to_user(err)
            return False

    def setup_database(self):
        try:
            if not self.is_database_valid():
                self.close_connection()
                raise sqlite3.NotSupportedError("This database is not supported.")
            self.db_cursor.executescript(DatabaseManager.SQLITE_SCHEMA)
            self.db_connection.commit()
        except sqlite3.Error as err:
            self.show_errors_to_user(err)

    def validate_session_token(self, session_token : str) -> int:
        self.db_cursor.execute(
            "SELECT account_id FROM Sessions WHERE token = ?;", 
            (session_token,)
        )
        results = self.db_cursor.fetchall()
        if len(results) == 1:
            return results[0][0] # account_id
        else:
            return -1

    def does_username_exist(self, username : str) -> int:
        self.db_cursor.execute(
            "SELECT account_id FROM Accounts WHERE (username = ?);",
            (username,)
        )
        results = self.db_cursor.fetchall()
        if len(results) > 0:
            return results[0][0] # account_id
        else:
            return -1

    @db_transaction
    def login(self, username : str, password : str) -> str: # returns session token on success
        account_id = self.does_username_exist(username)
        if account_id == -1:
            raise WrongUsernamePasswordError("Username or password is wrong.")
        self.db_cursor.execute(
            "SELECT password, is_disabled FROM Accounts WHERE (account_id = ?);",
            (account_id,)
        )
        result = self.db_cursor.fetchone()
        password_in_db = result[0]
        is_disabled = result[1]
        if password_in_db != hashlib.sha512(password.encode(encoding="utf-8")).hexdigest():
            raise WrongUsernamePasswordError("Username or password is wrong.")
        if is_disabled:
            raise WrongUsernamePasswordError("Username or password is wrong.")
        dt_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        self.db_cursor.execute(
            "UPDATE Accounts SET last_login = ? WHERE (account_id = ?);",
            (dt_str, account_id)
        )
        self.db_connection.commit()
        self.db_cursor.execute(
            "SELECT token FROM Sessions WHERE (account_id = ?);",
            (account_id,)
        )        
        tokens = self.db_cursor.fetchall()
        if len(tokens) > 0:
            return tokens[0][0]
        else:
            token = secrets.token_urlsafe(50)
            self.db_cursor.execute(
                "INSERT INTO Sessions (token, when_created, account_id) VALUES (?, ?, ?)",
                (token, dt_str, account_id)
            )
            self.db_connection.commit()
            return token
    
    @db_transaction
    def logout(self, session_token : str) -> bool: # deletes the session token on success
        account_id = self.validate_session_token(session_token)
        if account_id == -1:
            raise InvalidSessionTokenError("Session token is not valid.")
        self.db_cursor.execute(
            "DELETE FROM Sessions WHERE (account_id = ?)",
            (account_id,)
        )
        self.db_connection.commit()
        return True

    @db_transaction
    def add_account(self, username : str, password : str, first_name : str, last_name : str) -> bool:
        if self.does_username_exist(username) != -1:
            raise ExistingUsernameError("This username exists already.")
        dt_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        self.db_cursor.execute(
            "INSERT INTO Accounts (username, password, first_name, last_name, when_joined) VALUES (?, ?, ?, ?, ?);", 
            (username, hashlib.sha512(password.encode(encoding="utf-8")).hexdigest(), first_name, last_name, dt_str)
        )
        self.db_connection.commit()
        return True

    @db_transaction
    def edit_account(self, session_token : str, username : str, password : str, first_name : str, last_name : str) -> bool:
        account_id = self.validate_session_token(session_token)
        if account_id == -1:   
            raise InvalidSessionTokenError("Session token is not valid.")
        suspected_account_id = self.does_username_exist(username)
        if suspected_account_id != -1 and suspected_account_id != account_id:
            raise ExistingUsernameError("This username exists already.")
        self.db_cursor.execute(
            "UPDATE Accounts SET username = ?, password = ?, first_name = ?, last_name = ? WHERE account_id = ?;",
            (username, hashlib.sha512(password.encode(encoding="utf-8")).hexdigest(), first_name, last_name, account_id)
        )
        self.db_connection.commit()
        return True

    @db_transaction
    def remove_account(self, session_token : str) -> bool:
        account_id = self.validate_session_token(session_token)
        if account_id == -1:
            raise InvalidSessionTokenError("Session token is not valid.")
        # we will not delete account, instead update it to deleted account.
        # since in case of deleting account we have to delete the corresponding  
        dt_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        self.db_cursor.execute(
            "UPDATE Accounts SET username = ?, password = ?, first_name = ?, last_name = ?, is_disabled = ?, when_deleted = ? WHERE account_id = ?;",
            (
                "DELETED_ACCOUNT_{}".format(account_id), 
                "DELETED_ACCOUNT_PASSWORD_{}".format(account_id),
                "DELETED",
                "ACCOUNT",
                1,
                dt_str,
                account_id
            )
        )
        self.db_connection.commit()
        return True

    def close_connection(self):
        self.db_connection.close()

    def show_errors_to_user(self, err):
        print(err)