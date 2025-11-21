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
        self.clients = {}
        self.client_cursors = {}
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
            # store client data in dictionary
            self.clients[addr[1]] = client_socket
            self.client_cursors[addr[1]] = "1.0"

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

    def send_file(self, client_id):
        header = f"VERSION: {self.doc_ver}" + DELIMITER + f"CURSOR: {self.client_cursors[client_id]}"
        content = DELIMITER.join(self.doc)
        data = header + DELIMITER + content
        self.clients[client_id].sendall(data.encode())

    def insert_char(self, line, idx, char, client_id):
        self.doc[line - 1] = self.doc[line - 1][:idx] + char + self.doc[line - 1][idx:]
        self.client_cursors[client_id] = str(line) + "." + str(idx+1)

    def do_enter(self, line, idx, client_id):
        self.doc.insert(line, "") # insert new line
        self.doc[line] = self.doc[line-1][idx:]
        self.doc[line-1] = self.doc[line-1][:idx] + "\n" # add newline char to current line and split it
        
        # update cursors    
        self.client_cursors[client_id] = str(line+1) + "." + str(0)
        for key in self.client_cursors.keys():
                l, i = self.client_cursors[key].split(".")
                if int(l) > line+1:
                    self.client_cursors[key] = str(int(l)+1) + "." + str(i) 

    def remove_char(self, line, idx, client_id):
        if idx < 0:
            if line == 1:
                return
            self.client_cursors[client_id] = str(line-1) + "." + str(len(self.doc[line-2])-1)
            self.doc[line-2] = self.doc[line-2][:-1] + self.doc[line-1] # remove newline char on prev line and add remains of the next line
            self.doc.pop(line-1) # remove current line

            for key in self.client_cursors.keys():
                l, i = self.client_cursors[key].split(".")
                if int(l) >= line:
                    self.client_cursors[key] = str(int(l)-1) + "." + str(i)    
            return
        self.doc[line - 1] = self.doc[line - 1][:idx] + self.doc[line - 1][idx + 1:]
        self.client_cursors[client_id] = str(line) + "." + str(idx)

    def process_op(self, op):
        opcode = op["opcode"]
        client_id = op["id"]
        ver = int(op["ver"])
        line = int(op["line"])
        idx = int(op["idx"])
        if opcode == "INSERT":
            print("Inserting character into the doc...")
            if op["char"].lower() not in ["return", "backspace", "space"]:
                # insert normal characters
                self.insert_char(line, idx, op["char"], client_id)
            if op["char"].lower() == "return":
                # insert newline character
                self.do_enter(line, idx, client_id)
            if op["char"].lower() == "space":
                # insert space
                self.insert_char(line, idx, " ", client_id)
            if op["char"].lower() == "backspace":
                self.remove_char(line, idx-1, client_id)
            # increment version
            self.doc_ver += 1
            # send updated file to every client
            for client_id in self.clients.keys():
                print("Sending file to clients...")
                self.send_file(client_id)
            print(self.doc)

        elif opcode == "CURSOR":
            match op["char"].lower():
                case "left":
                    if idx > 0:
                        idx -= 1
                    self.client_cursors[client_id] = str(line) + "." + str(idx)
                case "right":
                    if idx < len(self.doc[line-1]):
                        idx += 1
                    self.client_cursors[client_id] = str(line) + "." + str(idx)
                case "up":
                    if line > 1:
                        line -= 1
                        if len(self.doc[line-1]) < idx:
                            idx = len(self.doc[line-1])
                    self.client_cursors[client_id] = str(line) + "." + str(idx)
                case "down":
                    if line < len(self.doc):
                        line += 1
                        if len(self.doc[line-1]) < idx:
                            idx = len(self.doc[line-1])
                    self.client_cursors[client_id] = str(line) + "." + str(idx)
            print("Sending cursor status to client...")
            self.send_file(client_id)

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


