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
        self.client.settimeout(10)
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
        while not self.shutdown_event.is_set() and listening_badger.is_cool():
            try:
                if not listening_badger.is_cool():
                    listening_badger.not_cool()
                    break
                message = self.client.recv(1024).decode(ASCII)
                if message.startswith('Entry forbidden'):
                    self.shutdown(f"Disconnected: {message}", 0)
                print(message)
                listening_badger.squeak()
            except KeyboardInterrupt:
                self.shutdown("See ya later, shitlords!", 0)
            except ConnectionRefusedError as ex:
                if ex.errno == errno.ECONNRESET:
                    self.shutdown("Server connection reset", 1)

    def graceful_shutdown(self):
        self.client.send("TERM".encode(ASCII))
        response = self.client.recv(1024).decode(ASCII).strip().lower()
        if response == "ACK":
            print(msg)
            self.shutdown_event.set()
            self.client.close()
            sys.exit(0)
        else:
            print("Server not ready to disconnect. Please try again.")

    def shutdown(self, msg, status):
        self.client.close()
        print(msg)
        sys.exit(status)

    def write(self):
        while not self.shutdown_event.is_set() and writing_badger.is_cool():
            try:
                if not writing_badger.is_cool():
                    writing_badger.not_cool()
                    break
                message = input("> ")
                self.client.send(message.encode(ASCII))
                writing_badger.squeak()
            except KeyboardInterrupt:
                print("Successfully caught keyboard interrupt; attempting graceful shutdown")
                self.graceful_shutdown()
            except ConnectionRefusedError as ex:
                if ex.errno == errno.ECONNRESET:
                    self.shutdown("Server connection lost", 1)

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
    port = args.port
    chat_client = ChatClient('127.0.0.1', port)
    try:
        if chat_client.connect():
            chat_client.run()
        else:
            chat_client.shutdown("Client shutdown")
    except KeyboardInterrupt:
        chat_client.shutdown("Client shutdown")
