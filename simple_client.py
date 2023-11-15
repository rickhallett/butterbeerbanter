import socket
import threading


class ChatClient:
    def __init__(self, host, port):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.port = port

    def connect(self):
        try:
            self.client.connect((self.host, self.port))
            print("Connected to the server.")
            return True
        except ConnectionRefusedError:
            print("Unable to connect to the server.")
            return False

    def receive(self):
        while True:
            try:
                message = self.client.recv(1024).decode('ascii')
                if message.strip() == 'Disconnected':
                    print('You have been disconnected')
                    self.client.close()
                    break
                print(message)
            except BaseException as ex:
                print("An error occurred!", ex)
                self.client.close()
                break

    def write(self):
        while True:
            message = input("> ")
            self.client.send(message.encode('ascii'))

    def run(self):
        # Starting Threads For Listening and Writing
        receive_thread = threading.Thread(target=self.receive)
        receive_thread.start()

        write_thread = threading.Thread(target=self.write)
        write_thread.start()


if __name__ == '__main__':
    # Create a chat client instance
    chat_client = ChatClient('127.0.0.1', 12346)

    # Attempt to connect to the server
    if chat_client.connect():
        chat_client.run()
