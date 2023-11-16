import socket
import threading
import argparse
import sys


class ChatClient:
    def __init__(self, host, port):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.port = port
        self.shutdown_event = threading.Event()

    def connect(self):
        try:
            self.client.connect((self.host, self.port))
            print("Connected to the server.")
            return True
        except ConnectionRefusedError:
            print("Unable to connect to the server.")
            return False

    def receive(self):
        while not self.shutdown_event.is_set():
            try:
                message = self.client.recv(1024).decode('ascii')
                if message.startswith('Entry forbidden'):
                    self.shutdown(f"Disconnected: {message}", 0)
                print(message)
            except KeyboardInterrupt:
                self.shutdown("See ya later, shitlords!", 0)

    def shutdown(self, msg, status):
        print(msg)
        self.shutdown_event.set()
        self.client.close()
        sys.exit(status)

    def write(self):
        while not self.shutdown_event.is_set():
            try:
                message = input("> ")
                self.client.send(message.encode('ascii'))
            except KeyboardInterrupt:
                self.shutdown("See ya later, shitlords", 0)

    def run(self):
        receive_thread = threading.Thread(target=self.receive, daemon=True)
        receive_thread.start()
        write_thread = threading.Thread(target=self.write, daemon=True)
        write_thread.start()


def parse_arguments():
    parser = argparse.ArgumentParser(description='Optional port argument.')
    parser.add_argument('--port', type=int, default=8080, help='Optional port number (default: 8080)')
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = parse_arguments()
    port = args.port
    chat_client = ChatClient('127.0.0.1', port)
    if chat_client.connect():
        chat_client.run()
    else:
        chat_client.shutdown("Client shutdown")
