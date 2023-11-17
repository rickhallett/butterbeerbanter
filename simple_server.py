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

    def __init__(self, client_socket, address, broadcaster, disconnecter, username):
        self.socket = client_socket
        self.address = address
        self.broadcast = broadcaster
        self.disconnect = disconnecter
        self.username = username
        self.has_left = False
        self.shutdown_event = threading.Event()
        self.receive_thread = threading.Thread(target=self.listen, daemon=True)
        self.receive_thread.start()

    def listen(self):
        last_message = None
        lives = 3
        while not self.shutdown_event.is_set():
            try:
                message = self.socket.recv(1024).decode(ASCII).strip()
                if message == 'TERM':
                    print("received TERM")
                    self.close()
                if message == "":
                    lives -= 1
                if lives == 0:
                    self.close()
                if message != last_message:
                    self.broadcast(self, message)
                    last_message = message
            except KeyboardInterrupt:
                self.close()
            except ConnectionResetError as e:
                print("CONNECTION RESET ERROR!!!!", e)
                self.close(can_msg=False)
            except BrokenPipeError as e:
                print("BROKEN PIPE ERROR!!!", e)
                self.close()
            except ConnectionError as e:
                print("CONNECTION ERROR!!!", e)
                self.close()
            except OSError as ex:
                if ex.errno == errno.EBADFD:
                    print("BAD FILE DESCRIPTOR!", ex)
                else:
                    print("SOME OTHER OS BULLSHIT!!", ex)

    def send(self, msg):
        try:
            self.socket.send(msg.encode(ASCII))
        except AttributeError as e:
            print("ATTRIBUTE ERROR", e, msg)

    def recv(self):
        return self.socket.recv(1024).decode(ASCII).lower().strip()

    def close(self, can_msg=True):
        self.shutdown_event.set()
        self.disconnect(self, can_msg)
        self.socket.close()


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
        tester = 0
        while True:
            client_socket, address = self.server.accept()
            tester += 1
            # TODO: authentication logic, get username for announcement

            if True:
                client = Client(client_socket, address, self.broadcast, self.disconnect, "tester{0}".format(tester))
                self.clients.append(client)
                self.announce(client, f'{client.username} has joined the chatroom')
                print(f"Connected with {str(address)}")
                continue

            client_socket.send("Login or Registration? (L) (R)".encode(ASCII))
            choice = client_socket.recv(1024).decode().strip().lower()
            try:
                username, status = self.user_manager.handle_choice(client_socket, choice)
            except UserManagerError as e:
                if e == 'UNIQUE constraint failed: users.username':  # TODO check string
                    self.reject_connection(client_socket, "Username already taken")
            except BrokenPipeError as e:
                print("BROKEN PIPE ERROR!!", e)
            except ConnectionResetError as e:
                print("CONNECTION RESET ERROR!!!", e)
            except ConnectionError as e:
                print("CONNECTION ERROR!!!", e)

            if status != 'success':
                self.reject_connection(client_socket, status)
            else:
                client = Client(client_socket, address, self.broadcast, self.disconnect, username)
                self.clients.append(client)
                self.announce(client, f'{client.username} has joined the chatroom')
                print(f"Connected with {str(address)}")

    @staticmethod
    def reject_connection(client_socket, reason):
        client_socket.send(f'Entry forbidden. ${reason}\nDisconnected'.encode(ASCII))
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
            client.send(msg.encode(ASCII))
            client.close()


def parse_arguments():
    parser = argparse.ArgumentParser(description='Optional port argument.')
    parser.add_argument('--port', type=int, default=8080, help='Optional port number (default: 8080)')
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    try:
        args = parse_arguments()
        port = args.port
        chat_server = ChatServer('127.0.0.1', port, 'chat_server.db')  # TODO: auto port?
        chat_server.run()
    except KeyboardInterrupt:
        print("Closing server. Next time!")
        chat_server.shutdown("Server has shutdown. Disconnected.")
        sys.exit(0)
    except OSError as ex:
        if ex.errno == errno.EADDRINUSE:
            print(ex)

# if __name__ == '__main__':
#     def try_port(next_port=None):
#         try:
#             args = parse_arguments()
#             port = next_port or args.port
#             chat_server = ChatServer('127.0.0.1', port, 'chat_server.db')  # TODO: auto port?
#             chat_server.run()
#         except KeyboardInterrupt:
#             print("Closing server. Next time!")
#             chat_server.shutdown("Server has shutdown. Disconnected.")
#             sys.exit(0)
#         except OSError as ex:
#             if ex.errno == errno.EADDRINUSE:
#                 new_port = port + 1
#                 print(f'{port} already in use. Trying port {new_port}')
#                 try_port(new_port)
