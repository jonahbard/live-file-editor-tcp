import argparse
import socket
import tkinter as tk
import json

document = ""
version = 0
client_socket = None

def receive_file():
    global client_socket
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

def display_file(text_widget):
    # clear the tkinter window, show contents of the doc
    global document
    text_widget.delete("1.0", tk.END)
    text_widget.insert("1.0", "".join(document))

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
            print(document)
    except FileNotFoundError:
        print("File not found...")

def key_handler(event, text_widget):

    if event.char and len(event.char) == 1:
        # get current index of the insert cursor in the window
        line, idx = text_widget.index(tk.INSERT).split('.')

        # construct operation packet
        op = {
            "opcode": "INSERT",
            "line": line,
            "idx": idx,
            "char": event.keysym
        }

        # send operation through the socket
        global client_socket
        json_str = json.dumps(op) + "\n" # adding terminating character
        client_socket.sendall(json_str.encode())

def start_gui():
    # Gemini was used to develop this GUI code
    window = tk.Tk()
    window.title("Live Text Editor")
    window.geometry("800x600")

    # Add save file button
    save_button = tk.Button(window, text="Save", command=write_file)
    save_button.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

    # adding text editing space
    text_widget = tk.Text(window)
    text_widget.pack(expand=True, fill="both")

    # bind key press to event handler
    text_widget.bind("<Key>", lambda e: key_handler(e, text_widget))
    # start the GUI update
    window.mainloop()

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
    start_gui()