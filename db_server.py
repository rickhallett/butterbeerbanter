import socket
import sys
import threading
import sqlite3
import argparse

ASCII = 'ascii'


class UserManagerError(BaseException):
    pass


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
                print('status after register', status)
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
        print('registering')
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
        self.shutdown_event = threading.Event()
        self.receive_thread = threading.Thread(target=self.listen, daemon=True)
        self.receive_thread.start()

    def listen(self):
        while not self.shutdown_event.is_set():
            try:
                message = self.socket.recv(1024).decode(ASCII).strip()
                print(message)
                self.broadcast(self, message)
            except KeyboardInterrupt:
                self.disconnect()
                self.shutdown_event.set()

    def send(self, msg):
        self.socket.send(msg.encode(ASCII))

    def recv(self):
        return self.socket.recv(1024).decode(ASCII).lower().strip()

    def close(self):
        self.disconnect(self)
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
        while True:
            client_socket, address = self.server.accept()
            # TODO: authentication logic, get username for announcement
            client_socket.send("Login or Registration? (L) (R)".encode(ASCII))
            choice = client_socket.recv(1024).decode().strip().lower()
            try:
                username, status = self.user_manager.handle_choice(client_socket, choice)
            except UserManagerError as e:
                if e == 'UNIQUE constraint failed: users.username':
                    self.reject_connection(client_socket, "Username already taken")

            if status != 'success':
                self.reject_connection(client_socket, status)
            else:
                client = Client(client_socket, address, self.broadcast, self.disconnect, username)
                print(client.username)
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
        print('broadcast', sender, message)
        for client in self.clients:
            if client is not sender:
                client.send(str(f'{sender.username}: {message}'))

    def disconnect(self, client):
        self.clients.remove(client)
        self.announce(f'{client.username} has left the chatroom')
        client.send('Disconnected'.encode(ASCII))
        client.close()

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
        chat_server = ChatServer('127.0.0.1', port, 'chat_server.db')
        chat_server.run()
    except KeyboardInterrupt:
        print("Closing server. Next time!")
        chat_server.shutdown("Server has shutdown. Disconnected.")
        sys.exit(0)
