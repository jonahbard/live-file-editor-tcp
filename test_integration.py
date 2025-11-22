import pytest
import socket
import threading
import time
import json
from server import Server
from client import Client

DELIMITER = "\u001D"

class TestIntegration:
    """Integration tests for client-server communication"""

    @pytest.fixture
    def server_port(self):
        """Get an available port for testing"""
        # Create a temporary socket to find an available port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        return port

    @pytest.fixture
    def running_server(self, server_port):
        """Start a test server"""
        server = Server('127.0.0.1', server_port)
        server.doc = ["hello world\n", "line two"]

        # Start server threads
        main_thread = threading.Thread(target=server.connection_listener, daemon=True)
        updater_thread = threading.Thread(target=server.doc_updater, daemon=True)
        main_thread.start()
        updater_thread.start()

        # Give server time to start
        time.sleep(0.1)

        yield server

        # Cleanup
        server.server_socket.close()

    def test_client_connection(self, running_server, server_port):
        """Test that a client can connect and receive an ID"""
        client = Client('127.0.0.1', server_port)

        assert client.id is not None
        assert isinstance(client.id, int)
        assert client.id in running_server.clients

        client.client_socket.close()

    def test_client_receives_initial_doc(self, running_server, server_port):
        """Test that client receives the initial document"""
        client = Client('127.0.0.1', server_port)

        # Start receiver thread
        receiver = threading.Thread(target=client.receive_file, daemon=True)
        receiver.start()

        # Send initial doc to client
        running_server.send_file(client.id)

        # Wait for client to receive
        time.sleep(0.2)

        with client.lock:
            assert client.doc == running_server.doc
            assert client.doc_version == running_server.doc_ver

        client.client_socket.close()

    def test_client_sends_operation(self, running_server, server_port):
        """Test that client can send an operation that server processes"""
        client = Client('127.0.0.1', server_port)

        # Start receiver thread
        receiver = threading.Thread(target=client.receive_file, daemon=True)
        receiver.start()

        # Get initial doc
        running_server.send_file(client.id)
        time.sleep(0.2)

        initial_doc_ver = running_server.doc_ver

        # Send an insert operation
        op = {
            "opcode": "MODIFY",
            "line": "1",
            "idx": "0",
            "char": "X",
            "ver": client.doc_version,
            "id": client.id
        }
        json_str = json.dumps(op) + DELIMITER
        client.client_socket.sendall(json_str.encode())

        # Wait for server to process
        time.sleep(0.3)

        assert running_server.doc[0].startswith("X")
        assert running_server.doc_ver == initial_doc_ver + 1

        client.client_socket.close()

    def test_multiple_clients_sync(self, running_server, server_port):
        """Test that multiple clients stay synchronized"""
        client1 = Client('127.0.0.1', server_port)
        client2 = Client('127.0.0.1', server_port)

        # Start receiver threads
        receiver1 = threading.Thread(target=client1.receive_file, daemon=True)
        receiver2 = threading.Thread(target=client2.receive_file, daemon=True)
        receiver1.start()
        receiver2.start()

        # Send initial docs
        running_server.send_file(client1.id)
        running_server.send_file(client2.id)
        time.sleep(0.2)

        # Client 1 sends an operation
        op = {
            "opcode": "MODIFY",
            "line": "1",
            "idx": "0",
            "char": "A",
            "ver": client1.doc_version,
            "id": client1.id
        }
        json_str = json.dumps(op) + DELIMITER
        client1.client_socket.sendall(json_str.encode())

        # Wait for propagation
        time.sleep(0.3)

        # Both clients should have the same document
        with client1.lock:
            doc1 = client1.doc.copy()
            ver1 = client1.doc_version

        with client2.lock:
            doc2 = client2.doc.copy()
            ver2 = client2.doc_version

        assert doc1 == doc2
        assert ver1 == ver2
        assert doc1[0].startswith("A")

        client1.client_socket.close()
        client2.client_socket.close()

    def test_cursor_synchronization(self, running_server, server_port):
        """Test that cursor positions are tracked for multiple clients"""
        client1 = Client('127.0.0.1', server_port)
        client2 = Client('127.0.0.1', server_port)

        receiver1 = threading.Thread(target=client1.receive_file, daemon=True)
        receiver2 = threading.Thread(target=client2.receive_file, daemon=True)
        receiver1.start()
        receiver2.start()

        running_server.send_file(client1.id)
        running_server.send_file(client2.id)
        time.sleep(0.2)

        # Client 1 moves cursor
        op = {
            "opcode": "CURSOR",
            "line": "1",
            "idx": "5",
            "char": "right",
            "ver": client1.doc_version,
            "id": client1.id
        }
        json_str = json.dumps(op) + DELIMITER
        client1.client_socket.sendall(json_str.encode())

        time.sleep(0.2)

        # Check that client 1's cursor position is updated on server
        assert running_server.client_cursors[client1.id] == "1.6"

        # Client 2's cursor should not have changed
        assert running_server.client_cursors[client2.id] == "1.0"

        client1.client_socket.close()
        client2.client_socket.close()

    def test_insert_updates_other_cursors_integration(self, running_server, server_port):
        """Test that when one client inserts, other cursors are updated"""
        client1 = Client('127.0.0.1', server_port)
        client2 = Client('127.0.0.1', server_port)

        receiver1 = threading.Thread(target=client1.receive_file, daemon=True)
        receiver2 = threading.Thread(target=client2.receive_file, daemon=True)
        receiver1.start()
        receiver2.start()

        running_server.send_file(client1.id)
        running_server.send_file(client2.id)
        time.sleep(0.2)

        # Position client 2's cursor at index 5
        running_server.client_cursors[client2.id] = "1.5"

        # Client 1 inserts at index 3
        op = {
            "opcode": "MODIFY",
            "line": "1",
            "idx": "3",
            "char": "X",
            "ver": client1.doc_version,
            "id": client1.id
        }
        json_str = json.dumps(op) + DELIMITER
        client1.client_socket.sendall(json_str.encode())

        time.sleep(0.3)

        # Client 2's cursor should have moved forward
        assert running_server.client_cursors[client2.id] == "1.6"

        client1.client_socket.close()
        client2.client_socket.close()

    def test_backspace_line_break(self, running_server, server_port):
        """Test backspace at start of line (removing line break)"""
        client = Client('127.0.0.1', server_port)

        receiver = threading.Thread(target=client.receive_file, daemon=True)
        receiver.start()

        running_server.send_file(client.id)
        time.sleep(0.2)

        initial_doc_length = len(running_server.doc)

        # Send backspace at start of line 2 (idx will be 0, server interprets as -1)
        op = {
            "opcode": "MODIFY",
            "line": "2",
            "idx": "0",
            "char": "backspace",
            "ver": client.doc_version,
            "id": client.id
        }
        json_str = json.dumps(op) + DELIMITER
        client.client_socket.sendall(json_str.encode())

        time.sleep(0.3)

        # Document should have one less line
        assert len(running_server.doc) == initial_doc_length - 1

        client.client_socket.close()

    def test_enter_key(self, running_server, server_port):
        """Test enter/return key creates new line"""
        client = Client('127.0.0.1', server_port)

        receiver = threading.Thread(target=client.receive_file, daemon=True)
        receiver.start()

        running_server.send_file(client.id)
        time.sleep(0.2)

        initial_doc_length = len(running_server.doc)

        # Send return/enter at middle of line
        op = {
            "opcode": "MODIFY",
            "line": "1",
            "idx": "5",
            "char": "return",
            "ver": client.doc_version,
            "id": client.id
        }
        json_str = json.dumps(op) + DELIMITER
        client.client_socket.sendall(json_str.encode())

        time.sleep(0.3)

        # Document should have one more line
        assert len(running_server.doc) == initial_doc_length + 1
        # First line should end with newline
        assert running_server.doc[0].endswith("\n")

        client.client_socket.close()

    def test_sequence_of_operations(self, running_server, server_port):
        """Test a realistic sequence of typing operations"""
        client = Client('127.0.0.1', server_port)

        receiver = threading.Thread(target=client.receive_file, daemon=True)
        receiver.start()

        running_server.doc = [""]
        running_server.send_file(client.id)
        time.sleep(0.2)

        # Type "hello"
        chars = ["h", "e", "l", "l", "o"]
        for i, char in enumerate(chars):
            op = {
                "opcode": "MODIFY",
                "line": "1",
                "idx": str(i),
                "char": char,
                "ver": client.doc_version,
                "id": client.id
            }
            json_str = json.dumps(op) + DELIMITER
            client.client_socket.sendall(json_str.encode())
            time.sleep(0.1)

        time.sleep(0.3)

        assert running_server.doc[0] == "hello"

        # Add space
        op = {
            "opcode": "MODIFY",
            "line": "1",
            "idx": "5",
            "char": "space",
            "ver": client.doc_version,
            "id": client.id
        }
        json_str = json.dumps(op) + DELIMITER
        client.client_socket.sendall(json_str.encode())
        time.sleep(0.2)

        assert running_server.doc[0] == "hello "

        # Type "world"
        start_idx = 6
        chars = ["w", "o", "r", "l", "d"]
        for i, char in enumerate(chars):
            op = {
                "opcode": "MODIFY",
                "line": "1",
                "idx": str(start_idx + i),
                "char": char,
                "ver": client.doc_version,
                "id": client.id
            }
            json_str = json.dumps(op) + DELIMITER
            client.client_socket.sendall(json_str.encode())
            time.sleep(0.1)

        time.sleep(0.3)

        assert running_server.doc[0] == "hello world"

        client.client_socket.close()

    def test_client_file_operations(self, tmp_path):
        """Test client file read/write operations (no server needed)"""
        test_file = tmp_path / "client_test.txt"

        # Create a client without connecting (just test file methods)
        client = Client.__new__(Client)
        client.doc = ["hello\n", "world"]

        client.write_file(str(test_file))

        # Reset and read back
        client.doc = []
        client.open_file(str(test_file))

        assert client.doc == ["hello\n", "world"]

    def test_client_file_not_found(self):
        """Test client handling of missing file"""
        client = Client.__new__(Client)
        client.doc = ["original"]

        client.open_file("/nonexistent/file.txt")

        # Doc should remain unchanged
        assert client.doc == ["original"]
