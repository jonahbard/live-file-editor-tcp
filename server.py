import socket
import threading
import argparse
from queue import Queue
import time 
import json

DELIMITER = "\u001D"
TIMEOUT = 60 # SECONDS



class Server(object):
    def __init__(self, host, port):
        # define instance vars
        self.doc = [""] * 10 # 200 empty lines to start
        self.doc_ver = 0
        self.clients = []
        self.data_lock = threading.Lock()
        self.op_queue = Queue()

        # bind socket to ip with given port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((host, port))

        self.server_socket.listen()
        print(f"Server listening on {host}:{port}...")

    def connection_listener(self):
        # listen for new connections
        while True:
            # get ip and port
            client_socket, addr = self.server_socket.accept() 

            # store client data in list
            self.clients.append((client_socket, addr))
            
            # start new thread for newly connected client
            thread = threading.Thread(target=self.connection_handler, args=(client_socket, addr))
            thread.start()

    def connection_handler(self, client_socket, addr):
        print(f"(New Thread) Connected by {addr}")
        local_ip, local_port = client_socket.getsockname()
        print(f"Using IP {local_ip} and port {local_port} for this client")

        start = time.thread_time()
        # receive data and process into cmd code and url
        while time.thread_time() - start < TIMEOUT:
            data = client_socket.recv(4096)
            if data:
                print(f"Server received data: {data}")
                arr = data.decode("utf-8", errors='ignore').split(DELIMITER)
                for elem in arr:
                    if elem: self.op_queue.put(json.loads(elem))
                    start = time.thread_time() # restart timeout timer

        client_socket.close()

    def write_file(self, filename="server_file.txt"):
        with open(filename, 'w') as f:
            # writes the lines into a file on disk 
            f.writelines(self.doc)

    def open_file(self, filename="server_file.txt"):
        try:
            with open(filename, 'r') as f:
                # obtains a list of lines as strings in a file (includes terminating \n)
                self.doc = f.readlines()
        except FileNotFoundError:
            print("File not found...")

    def send_file(self, client_socket):
        header = f"VERSION: {self.doc_ver}"
        content = DELIMITER.join(self.doc)
        data = header + DELIMITER + content
        client_socket.sendall(data.encode())

    def process_op(self, op):
        line = int(op["line"])
        idx = int(op["idx"])
        if op["char"].lower() not in ["return", "backspace", "space"]:
            print("Inserting character into the doc...")
            self.doc[line - 1] = self.doc[line - 1][:idx] + op["char"] + self.doc[line - 1][idx:]
        # TODO: handle enter and backspace

        # increment version
        self.doc_ver += 1

        # send updated file to every client
        for (socket, addr) in self.clients:
            print("Sending file to clients...")
            self.send_file(socket)

    def doc_updater(self):
        while True:
            if self.op_queue:
                print("Processing operations...")
                self.process_op(self.op_queue.get())


def main():
    # parse the arguments with server port and ip
    parser = argparse.ArgumentParser()
    parser.add_argument("host", help="Server's IP address")
    parser.add_argument("port", help="Server's port number")
    args = parser.parse_args()

    # define host ip and port
    HOST = args.host
    PORT = int(args.port)

    server = Server(HOST, PORT)

    # start a listener thread for the server
    try:
        main_thread = threading.Thread(target=server.connection_listener, daemon=True, name="main_thread")
        updater_thread = threading.Thread(target=server.doc_updater, daemon=True, name="updater_thread")
        main_thread.start()
        updater_thread.start()
        main_thread.join()
        updater_thread.join()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server.server_socket.close()
        print("Done.")

if __name__ == "__main__":
    main()


