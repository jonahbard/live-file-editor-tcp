import argparse
import socket
import tkinter as tk
from tkinter import scrolledtext

document = ""
version = 0

def receive_file(client_socket):
    # Receive response in chunks and concatenate
    response = b""
    while True:
        chunk = client_socket.recv(1460)
        if not chunk:
            break   
        response += chunk
    client_socket.close()

    # Decode and update current document version
    global document
    global version
    document = response.decode("utf-8", errors="ignore")
    version += 1 # TODO: obtain version from the received data 

def write_file(filename="client_file.txt"):
    with open(filename, 'w') as f:
        global document
        # writes the lines into a file on disk 
        f.writelines(document)

def open_file(filename="client_file.txt"):
    try:
        with open(filename, 'r') as f:
            global document
            # obtains a list of lines as strings in a file (includes terminating \n)
            document = f.readlines()
    except FileNotFoundError:
        print("File not found...")

def draw_gui():
    # Gemini was used to develop this GUI code
    root_window = tk.Tk()
    root_window.title("Live Text Editor")
    root_window.geometry("800x600")

    # Add save file button
    save_button = tk.Button(root_window, text="Save", command=write_file)
    save_button.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

    # adding text editing space
    text_area = scrolledtext.ScrolledText(root_window, wrap=tk.WORD, font=("Consolas", 12))
    text_area.pack(expand=True, fill="both")

    # start the GUI update
    root_window.mainloop()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("host", help="Server IP address")
    parser.add_argument("port", help="Server listener port")
    parser.add_argument("filename", help="Filepath of file to request")

    args = parser.parse_args()

    # define host ip and port
    HOST = args.host
    PORT = int(args.port)

    # Create a TCP socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((HOST, PORT))

if __name__ == "__main__":
    draw_gui()