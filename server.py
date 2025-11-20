import socket
import threading
import argparse

# define globals
document = ""
version = 0
clients = []
data_lock = threading.Lock()

def connection_listener(server_socket):
    # listen for new connections
    while True:
        # get ip and port
        client_socket, addr = server_socket.accept() 

        # store client data in list
        global clients
        clients.append((client_socket, addr))
        
        # start new thread for newly connected client
        thread = threading.Thread(target=connection_handler, args=(client_socket, addr))
        thread.start()

        # TODO: periodically send updated file to each client

def connection_handler(client_socket, addr):
    print(f"(New Thread) Connected by {addr}")
    local_ip, local_port = client_socket.getsockname()
    print(f"Using IP {local_ip} and port {local_port} for this client")

    # receive data and process into cmd code and url
    while True:
        # TODO: process data from client according to the packet received
        data = client_socket.recv(1460)
    
    client_socket.close()

def write_file(filename="server_file.txt"):
    with open(filename, 'w') as f:
        global document
        # writes the lines into a file on disk 
        f.writelines(document)

def open_file(filename="server_file.txt"):
    try:
        with open(filename, 'r') as f:
            global document
            # obtains a list of lines as strings in a file (includes terminating \n)
            document = f.readlines()
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

    # bind socket to ip with given port
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))

    server_socket.listen()
    print(f"Server listening on {HOST}:{PORT}...")

    # start a listener thread for the server
    try:
        main_thread = threading.Thread(target=connection_listener, args=(server_socket,), daemon=True, name="main_thread")
        main_thread.start()
        main_thread.join()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server_socket.close()
        print("Done.")

if __name__ == "__main__":
    main()


