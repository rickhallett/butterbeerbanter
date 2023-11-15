import socket
import threading
import sqlite3

ASCII = 'ascii'


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

    def register_new_user(self, username, password):
        try:
            self.cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def authenticate_user(self, username, password):
        self.cursor.execute('SELECT password FROM users WHERE username = ?', (username,))
        result = self.cursor.fetchone()
        if result and result[0] == password:
            return True
        else:
            return False


class Client:

    def __init__(self, client_socket, address, broadcaster, disconnecter, username):
        self.socket = client_socket
        self.address = address
        self.broadcast = broadcaster
        self.disconnect = disconnecter
        self.username = username

        self.receive_thread = threading.Thread(target=self.listen)
        self.receive_thread.start()

        # self.write_thread = threading.Thread(target=self.write)
        # self.write_thread.start()

    # def start_listening(self):
    #     self.receive_thread.start()
    #     self.write_thread.start()

    def listen(self):
        while True:
            try:
                message = self.socket.recv(1024).decode(ASCII).strip()
                print(message)
                self.broadcast(self, message)
            except BaseException as ex:
                print(ex)
                self.disconnect()
                break

    # def write(self):
    #     while True:
    #         message = input("> ")
    #         self.broadcast(self, message)

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
            username = 'mr blobby'
            password = 'blobbyblobbyblobby'
            client = Client(client_socket, address, self.broadcast, self.disconnect, username)
            print(client.username)
            self.clients.append(client)
            self.announce(client, f'{client.username} has joined the chatroom')
            print(f"Connected with {str(address)}")

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


if __name__ == '__main__':
    chat_server = ChatServer('127.0.0.1', 12346, 'chat_server.db')
    chat_server.run()
