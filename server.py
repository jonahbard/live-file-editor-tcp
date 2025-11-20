import socket
import threading
import argparse

class Server(object):
    def __init__(self, host, port):
        # define instance vars
        self.doc = ""
        self.doc_ver = 0
        self.clients = []
        self.data_lock = threading.Lock()

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

            # TODO: periodically send updated file to each client

    def connection_handler(self, client_socket, addr):
        print(f"(New Thread) Connected by {addr}")
        local_ip, local_port = client_socket.getsockname()
        print(f"Using IP {local_ip} and port {local_port} for this client")

        # receive data and process into cmd code and url
        while True:
            # TODO: process data from client according to the packet received
            data = client_socket.recv(1460)
        
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


def main():
    # parse the arguments with server port and ip
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True, help="Server's IP address")
    parser.add_argument("--port", required=True, help="Server's port number")
    args = parser.parse_args()

    # define host ip and port
    HOST = args.host
    PORT = int(args.port)

    server = Server(HOST, PORT)

    # start a listener thread for the server
    try:
        main_thread = threading.Thread(target=server.connection_listener, daemon=True, name="main_thread")
        main_thread.start()
        main_thread.join()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server.server_socket.close()
        print("Done.")

if __name__ == "__main__":
    main()


