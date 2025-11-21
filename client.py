import argparse
import socket
import tkinter as tk
import json

DELIMITER = "\u001D"

class Client(object):

    def __init__(self, host, port):
        # Create a TCP socket
        # self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # self.client_socket.connect((host, port))

        self.doc = None
        self.doc_version = 0

    def receive_file(self):
        # Receive response in chunks and concatenate
        response = b""
        while True:
            chunk = self.client_socket.recv(1460)
            if not chunk:
                break   
            response += chunk

        # Decode and update current document version
        data = response.decode("utf-8", errors="ignore").split(DELIMITER)
        self.doc_version = int(data[0].strip("VERSION: "))
        self.doc = data[1:]
        self.display_file()

    def display_file(self):
        # clear the tkinter window, show contents of the doc
        self.text_widget.delete("1.0", tk.END)
        self.text_widget.insert("1.0", "".join(self.doc))
        print("displayed file")

    def write_file(self, filename="client_file.txt"):
        with open(filename, 'w') as f:
            # writes the lines into a file on disk 
            f.writelines(self.doc)

    def open_file(self, filename="client_file.txt"):
        try:
            with open(filename, 'r') as f:
                # obtains a list of lines as strings in a file (includes terminating \n)
                self.doc = f.readlines()
                self.display_file()
        except FileNotFoundError:
            print("File not found...")

class GUI(object):

    def __init__(self, client):
        
        self.client = client
        # Gemini was used to develop this GUI code
        self.window = tk.Tk()
        self.window.title("Live Text Editor")
        self.window.geometry("800x600")

        # Add save file button
        self.save_button = tk.Button(self.window, text="Save", command=client.write_file)
        self.save_button.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # adding text editing space
        self.text_widget = tk.Text(self.window)
        self.text_widget.pack(expand=True, fill="both")

        self.client.text_widget = self.text_widget

        # bind key press to event handler
        self.text_widget.bind("<Key>", self.key_handler)


    def run(self):
        self.window.mainloop()

    def get_text_widget(self):
        return self.text_widget
    
    def key_handler(self, event):

        if event.char and len(event.char) == 1:
            # get current index of the insert cursor in the window
            line, idx = self.text_widget.index(tk.INSERT).split('.')

            # construct operation packet
            op = {
                "opcode": "INSERT",
                "line": line,
                "idx": idx,
                "char": event.keysym
            }

            # send operation through the socket
            json_str = json.dumps(op) + DELIMITER # adding terminating character
            self.client.client_socket.sendall(json_str.encode())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("host", help="Server IP address")
    parser.add_argument("port", help="Server listener port")

    args = parser.parse_args()

    # define host ip and port
    HOST = args.host
    PORT = int(args.port)

    client = Client(HOST, PORT)
    screen = GUI(client)
    client.open_file()
    screen.run()
    

if __name__ == "__main__":
    main()
