import socket
import sys
import threading
import sqlite3
import argparse
import errno

from simple_client import BugBadger

ASCII = 'ascii'
max_loops = 10

listening_badger = BugBadger(50)


class UserManagerError(BaseException):  # delete this BS
    pass


class Debug:
    def __init__(self):
        self._bypass_db = False

    @property
    def bypass_db(self, val):
        return self._bypass_db

    @bypass_db.setter
    def bypass_db(self, val):
        if type(val) is bool:
            self._bypass_db = val
        else:
            raise AttributeError(f"type(val) must be bool")


debug = Debug()
debug.bypass_db = True


class UserManager:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.initialize_db()

    def initialize_db(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT
            )
        ''')
        self.conn.commit()

    def handle_choice(self, client, choice):
        client.send('Enter username'.encode(ASCII))
        username = client.recv(1024).decode().strip().lower()
        client.send('Enter password'.encode(ASCII))
        password = client.recv(1024).decode().strip().lower()
        status = None

        try:
            if choice == 'r':
                status = self.register_new_user(username, password)
                if status != 'success':
                    status = f'Registration failed: {status}'

            elif choice == 'l':
                status = self.authenticate_user(username, password)
                if status != 'success':
                    status = f'Login failed: {status}'
            else:
                client.send('Invalid selection'.encode(ASCII))
        except BaseException as ex:
            raise UserManagerError(f'Unknown error: {ex}')

        return username, status

    def register_new_user(self, username, password):
        try:
            self.cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            self.conn.commit()
            return 'success'
        except sqlite3.IntegrityError as e:
            return e

    def authenticate_user(self, username, password):
        self.cursor.execute('SELECT password FROM users WHERE username = ?', (username,))
        result = self.cursor.fetchone()
        if result and result[0] == password:
            return result
        else:
            return False


class Client:

    def __init__(self, client_socket, address, broadcaster, disconnecter, shutdown_server, username):
        self.socket = client_socket
        self.address = address
        self.broadcast = broadcaster
        self.disconnect = disconnecter
        self.shutdown_server = shutdown_server
        self.username = username
        self.has_left = False
        self.shutdown_event = threading.Event()
        self.receive_thread = threading.Thread(target=self.listen)
        self.receive_thread.start()

    def listen(self):
        last_message = None
        while not self.shutdown_event.is_set():
            try:
                message = self.socket.recv(1024).decode(ASCII).strip()
                if message != last_message:
                    self.broadcast(self, message)
                    last_message = message
            except KeyboardInterrupt:  # TODO: does not catch keyboard event
                print("keyboard interrupt")
                self.shutdown_server()
                self.close()
            except (ConnectionResetError, BrokenPipeError, ConnectionError) as e:
                print(e)
                self.close(can_msg=False)
            except OSError as e:
                if e.errno == errno.EBADF:
                    print(e)
                    self.close(can_msg=False)

    def send(self, msg):
        try:
            self.socket.send(msg.encode(ASCII))
        except AttributeError as e:
            print("ATTRIBUTE ERROR", e, msg)
        except BrokenPipeError as ex:
            print(ex)

    def recv(self):
        return self.socket.recv(1024).decode(ASCII).lower().strip()

    def close(self, can_msg=True):
        self.shutdown_event.set()
        self.disconnect(self, can_msg)
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
            self.socket.close()
        except OSError as ex:
            if ex.errno == errno.ENOTCONN:
                print("Socket no longer connected")


class ChatServer:
    def __init__(self, host, port, db_path):
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.host, self.port))
        self.server.listen()
        self.user_manager = UserManager(db_path)
        self.clients = []
        print(f"Server is listening on port {self.port}...")

    def run(self):
        while True:
            client_socket, address = self.server.accept()

            # if True:
            #     client = Client(client_socket, address, self.broadcast, self.disconnect, self.shutdown,
            #                     "tester{0}".format(tester))
            #     self.clients.append(client)
            #     self.announce(client, f'{client.username} has joined the chatroom')
            #     print(f"Connected with {str(address)}")
            #     continue

            client_socket.send("Login or Registration? (L) (R)".encode(ASCII))
            choice = client_socket.recv(1024).decode().strip().lower()
            try:
                username, status = self.user_manager.handle_choice(client_socket, choice)
            except (sqlite3.DataError, sqlite3.DatabaseError) as e:
                if e == 'UNIQUE constraint failed: users.username':  # TODO check string
                    self.reject_connection(client_socket, "Username already taken")
            except (BrokenPipeError, ConnectionResetError, ConnectionError) as e:
                print(e)
                self.disconnect(client_socket, can_msg=True, shutdown=True)

            if status != 'success':
                self.reject_connection(client_socket, status)
            else:
                client = Client(client_socket, address, self.broadcast, self.disconnect, self.shutdown, username)
                self.clients.append(client)
                self.announce(client, f'{client.username} has joined the chatroom')
                print(f"Connected with {str(address)}")

    @staticmethod
    def reject_connection(client_socket, reason):
        client_socket.send(f'Entry forbidden. ${reason}\nDisconnected'.encode(ASCII))
        client_socket.shutdown(socket.SHUT_RDWR)
        client_socket.close()

    def announce(self, joiner, message):
        for client in self.clients:
            if client is not joiner:
                client.send(message)

    def broadcast(self, sender, message):
        print('broadcast', message)
        for client in self.clients:
            if client is not sender:
                client.send(str(f'{sender.username}: {message}'))

    def disconnect(self, client, can_msg):
        if not client.has_left:
            self.clients.remove(client)
            client.has_left = True
            self.announce(client, f'{client.username} has left the chatroom')
            if can_msg:
                client.send('Disconnected')

    def shutdown(self, msg):
        for client in self.clients:
            client.send(msg)
            client.close()


def parse_arguments():
    parser = argparse.ArgumentParser(description='Optional port argument.')
    parser.add_argument('--port', type=int, default=8080, help='Optional port number (default: 8080)')
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = parse_arguments()
    initial_port = args.port


    def try_port(port):
        try:
            chat_server = ChatServer('127.0.0.1', port, 'chat_server.db')  # TODO: auto port?
            chat_server.run()
        except KeyboardInterrupt:  # TODO: does not catch keyboard event
            print("Closing server. Next time!")
            chat_server.shutdown("Server has shutdown. Disconnected.")
            sys.exit(0)
        except OSError as ex:
            if ex.errno == errno.EADDRINUSE:
                next_port = port + 1
                print(f'{port} already in use. Trying port {next_port}')
                try_port(next_port)


    try_port(initial_port)
