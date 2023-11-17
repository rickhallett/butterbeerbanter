import socket
import threading
import argparse
import sys
import errno

ASCII = 'ascii'


class BugBadger:

    def __init__(self, max_loops):
        self.max_loops = max_loops
        self.current_loops = 0

    def sooth(self):
        self.current_loops = self.max_loops

    def squeak(self):
        self.current_loops += 1

    def is_cool(self):
        return self.current_loops <= self.max_loops

    def not_cool(self):
        print("Badger not cool", self)


listening_badger = BugBadger(50)
writing_badger = BugBadger(50)


class ChatClient:
    def __init__(self, host, port):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.port = port
        self.shutdown_event = threading.Event()

    def connect(self):
        try:
            self.client.connect((self.host, self.port))
            print(f"Connected to the server on port {self.port}")
            return True
        except ConnectionRefusedError as ex:
            # print("Unable to connect to the server.", ex)
            print('raising')
            raise ConnectionRefusedError("Unable to connect to the server.")

    def receive(self):
        while not self.shutdown_event.is_set():
            try:
                message = self.client.recv(1024).decode(ASCII)
                if message.startswith('Entry forbidden'):
                    self.shutdown(f"Disconnected: {message}", 0)
                print(message)
            except KeyboardInterrupt:  # TODO: does not catch keyboard event
                self.shutdown("See ya later, shitlords!", 0)
            except ConnectionRefusedError as ex:
                if ex.errno == errno.ECONNRESET:
                    self.shutdown("Server connection reset", 1)
            except ConnectionResetError as ex:
                self.shutdown(ex, 1)

    def write(self):
        while not self.shutdown_event.is_set():
            try:
                message = input("> ")
                self.client.send(message.encode(ASCII))
            except KeyboardInterrupt:  # TODO: does not catch keyboard event
                print("Successfully caught keyboard interrupt; attempting graceful shutdown")
                self.graceful_shutdown()
            except ConnectionRefusedError as ex:
                if ex.errno == errno.ECONNRESET:
                    self.shutdown("Server connection lost", 1)
            except ConnectionResetError as ex:
                self.shutdown(ex, 1)

    def graceful_shutdown(self):
        self.client.send("TERM".encode(ASCII))
        response = self.client.recv(1024).decode(ASCII).strip().lower()
        if response == "ACK":
            self.shutdown_event.set()
            self.client.shutdown(socket.SHUT_RDWR)
            self.client.close()
            sys.exit(0)
        else:
            print("Server not ready to disconnect. Please try again.")

    def shutdown(self, msg, status):
        self.client.shutdown(socket.SHUT_RDWR)
        self.client.close()
        print(msg)
        sys.exit(status)

    def run(self):
        receive_thread = threading.Thread(target=self.receive)
        receive_thread.start()
        write_thread = threading.Thread(target=self.write)
        write_thread.start()


def parse_arguments():
    parser = argparse.ArgumentParser(description='Optional port argument.')
    parser.add_argument('--port', type=int, default=8080, help='Optional port number (default: 8080)')
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = parse_arguments()
    initial_port = args.port


    def try_port(port):
        chat_client = ChatClient('127.0.0.1', port)
        try:
            if chat_client.connect():
                chat_client.run()
            else:
                chat_client.shutdown("Client shutdown", 1)
        except KeyboardInterrupt:
            chat_client.shutdown("Client shutdown", 1)
        except ConnectionRefusedError as ex:
            next_port = port + 1
            print(f"{port} already in use. Trying port {next_port}")
            try_port(next_port)


    try_port(initial_port)
