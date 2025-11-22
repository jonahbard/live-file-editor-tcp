import pytest
import json
from server import Server

class TestServer:
    """Unit tests for Server document operations"""

    @pytest.fixture
    def server(self):
        """Create a server instance without starting socket"""
        # We'll create server without binding to avoid port conflicts
        server = Server.__new__(Server)
        server.doc = [""] * 10
        server.doc_ver = 0
        server.clients = {}
        server.client_cursors = {}
        return server

    def test_insert_char_basic(self, server):
        """Test basic character insertion"""
        server.client_cursors[1] = "1.0"
        server.doc[0] = "hello"

        server.insert_char(1, 0, "X", 1)

        assert server.doc[0] == "Xhello"
        assert server.client_cursors[1] == "1.1"

    def test_insert_char_middle(self, server):
        """Test inserting character in the middle of a line"""
        server.client_cursors[1] = "1.3"
        server.doc[0] = "hello"

        server.insert_char(1, 3, "X", 1)

        assert server.doc[0] == "helXlo"
        assert server.client_cursors[1] == "1.4"

    def test_insert_char_updates_other_cursors(self, server):
        """Test that inserting a char updates other clients' cursors on same line"""
        server.client_cursors[1] = "1.3"
        server.client_cursors[2] = "1.5"
        server.client_cursors[3] = "1.2"  # Before insertion point
        server.doc[0] = "hello world"

        server.insert_char(1, 3, "X", 1)

        assert server.client_cursors[1] == "1.4"  # Client who inserted moves forward
        assert server.client_cursors[2] == "1.6"  # Client after insertion moves forward
        assert server.client_cursors[3] == "1.2"  # Client before insertion stays same

    def test_remove_char_basic(self, server):
        """Test basic character removal"""
        server.client_cursors[1] = "1.5"
        server.doc[0] = "hello"

        server.remove_char(1, 4, 1)

        assert server.doc[0] == "hell"
        assert server.client_cursors[1] == "1.4"

    def test_do_enter_basic(self, server):
        """Test enter/newline insertion"""
        server.client_cursors[1] = "1.5"
        server.doc = ["hello world"]

        server.do_enter(1, 5, 1)

        assert server.doc[0] == "hello\n"
        assert server.doc[1] == " world"
        assert server.client_cursors[1] == "2.0"

    def test_do_enter_updates_cursors_below(self, server):
        """Test that enter updates cursors on lines below"""
        server.client_cursors[1] = "1.5"
        server.client_cursors[2] = "2.3"  # On line below
        server.client_cursors[3] = "1.3"  # Same line, before break
        server.doc = ["hello world", "line two"]

        server.do_enter(1, 5, 1)

        assert server.client_cursors[1] == "2.0"  # Client who hit enter
        assert server.client_cursors[2] == "3.3"  # Client on line below moved down
        assert server.client_cursors[3] == "2.3"  # Client same line before break moved down

    def test_do_enter_updates_cursors_after_on_same_line(self, server):
        """Test that enter updates cursors after insertion point on same line"""
        server.client_cursors[1] = "1.5"
        server.client_cursors[2] = "1.8"  # Same line, after break point
        server.doc = ["hello world"]

        server.do_enter(1, 5, 1)

        assert server.client_cursors[1] == "2.0"
        # Cursor was at index 8, line was split at 5, so new position is line 2, index (8-6+1)=3
        assert server.client_cursors[2] == "2.3"

    def test_remove_char_line_break(self, server):
        """Test removing a line break (backspace at start of line)"""
        server.client_cursors[1] = "2.0"
        server.doc = ["hello\n", "world"]

        server.remove_char(2, -1, 1)  # idx=-1 indicates line break

        assert len(server.doc) == 1
        assert server.doc[0] == "helloworld"
        assert server.client_cursors[1] == "1.5"  # Cursor moved to end of prev line

    def test_remove_char_line_break_first_line(self, server):
        """Test that backspace at start of first line does nothing"""
        server.client_cursors[1] = "1.0"
        server.doc = ["hello"]

        server.remove_char(1, -1, 1)

        assert server.doc == ["hello"]  # No change

    def test_remove_char_line_break_updates_cursors_below(self, server):
        """Test that removing line break updates cursors on lines below"""
        server.client_cursors[1] = "2.0"
        server.client_cursors[2] = "3.5"  # On line below
        server.doc = ["hello\n", "world\n", "line three"]

        server.remove_char(2, -1, 1)

        assert server.client_cursors[1] == "1.5"  # Client who deleted
        assert server.client_cursors[2] == "2.5"  # Client below moved up one line

    def test_remove_char_line_break_updates_cursor_on_merged_line(self, server):
        """Test that removing line break updates cursor on the line being merged"""
        server.client_cursors[1] = "2.0"
        server.client_cursors[2] = "2.3"  # On same line as client 1
        server.doc = ["hello\n", "world"]

        previous_line_len = len(server.doc[0])
        server.remove_char(2, -1, 1)

        # Client 2 was on line 2 at index 3, should now be on line 1 at previous_line_len + 3 - 1
        assert server.client_cursors[2] == f"1.{previous_line_len + 3 - 1}"

    def test_process_op_insert_normal_char(self, server):
        """Test processing a MODIFY operation with normal character"""
        server.client_cursors[1] = "1.0"
        server.clients[1] = None  # Mock client
        server.doc[0] = "hello"

        op = {
            "opcode": "MODIFY",
            "line": "1",
            "idx": "0",
            "char": "X",
            "ver": 0,
            "id": 1
        }

        # Mock send_file to avoid socket errors
        server.send_file = lambda x: None

        server.process_op(op)

        assert server.doc[0] == "Xhello"
        assert server.doc_ver == 1

    def test_process_op_space(self, server):
        """Test processing space character"""
        server.client_cursors[1] = "1.5"
        server.clients[1] = None
        server.doc[0] = "hello"
        server.send_file = lambda x: None

        op = {
            "opcode": "MODIFY",
            "line": "1",
            "idx": "5",
            "char": "space",
            "ver": 0,
            "id": 1
        }

        server.process_op(op)

        assert server.doc[0] == "hello "

    def test_process_op_return(self, server):
        """Test processing return/enter key"""
        server.client_cursors[1] = "1.5"
        server.clients[1] = None
        server.doc = ["hello"]
        server.send_file = lambda x: None

        op = {
            "opcode": "MODIFY",
            "line": "1",
            "idx": "5",
            "char": "return",
            "ver": 0,
            "id": 1
        }

        server.process_op(op)

        assert server.doc[0] == "hello\n"
        assert server.doc[1] == ""

    def test_process_op_backspace(self, server):
        """Test processing backspace"""
        server.client_cursors[1] = "1.5"
        server.clients[1] = None
        server.doc[0] = "hello"
        server.send_file = lambda x: None

        op = {
            "opcode": "MODIFY",
            "line": "1",
            "idx": "5",
            "char": "backspace",
            "ver": 0,
            "id": 1
        }

        server.process_op(op)

        assert server.doc[0] == "hell"

    def test_process_op_cursor_left(self, server):
        """Test cursor movement left"""
        server.client_cursors[1] = "1.5"
        server.clients[1] = None
        server.doc[0] = "hello"
        server.send_file = lambda x: None

        op = {
            "opcode": "CURSOR",
            "line": "1",
            "idx": "5",
            "char": "left",
            "ver": 0,
            "id": 1
        }

        server.process_op(op)

        assert server.client_cursors[1] == "1.4"

    def test_process_op_cursor_right(self, server):
        """Test cursor movement right"""
        server.client_cursors[1] = "1.3"
        server.clients[1] = None
        server.doc[0] = "hello"
        server.send_file = lambda x: None

        op = {
            "opcode": "CURSOR",
            "line": "1",
            "idx": "3",
            "char": "right",
            "ver": 0,
            "id": 1
        }

        server.process_op(op)

        assert server.client_cursors[1] == "1.4"

    def test_process_op_cursor_up(self, server):
        """Test cursor movement up"""
        server.client_cursors[1] = "2.3"
        server.clients[1] = None
        server.doc = ["hello", "world"]
        server.send_file = lambda x: None

        op = {
            "opcode": "CURSOR",
            "line": "2",
            "idx": "3",
            "char": "up",
            "ver": 0,
            "id": 1
        }

        server.process_op(op)

        assert server.client_cursors[1] == "1.3"

    def test_process_op_cursor_down(self, server):
        """Test cursor movement down"""
        server.client_cursors[1] = "1.3"
        server.clients[1] = None
        server.doc = ["hello", "world"]
        server.send_file = lambda x: None

        op = {
            "opcode": "CURSOR",
            "line": "1",
            "idx": "3",
            "char": "down",
            "ver": 0,
            "id": 1
        }

        server.process_op(op)

        assert server.client_cursors[1] == "2.3"

    def test_cursor_boundaries_left(self, server):
        """Test cursor left at start of line"""
        server.client_cursors[1] = "1.0"
        server.clients[1] = None
        server.doc[0] = "hello"
        server.send_file = lambda x: None

        op = {
            "opcode": "CURSOR",
            "line": "1",
            "idx": "0",
            "char": "left",
            "ver": 0,
            "id": 1
        }

        server.process_op(op)

        assert server.client_cursors[1] == "1.0"  # Should stay at 0

    def test_cursor_boundaries_right(self, server):
        """Test cursor right at end of line"""
        server.client_cursors[1] = "1.5"
        server.clients[1] = None
        server.doc[0] = "hello"
        server.send_file = lambda x: None

        op = {
            "opcode": "CURSOR",
            "line": "1",
            "idx": "5",
            "char": "right",
            "ver": 0,
            "id": 1
        }

        server.process_op(op)

        assert server.client_cursors[1] == "1.5"  # Should stay at end

    def test_cursor_boundaries_up(self, server):
        """Test cursor up at first line"""
        server.client_cursors[1] = "1.3"
        server.clients[1] = None
        server.doc = ["hello"]
        server.send_file = lambda x: None

        op = {
            "opcode": "CURSOR",
            "line": "1",
            "idx": "3",
            "char": "up",
            "ver": 0,
            "id": 1
        }

        server.process_op(op)

        assert server.client_cursors[1] == "1.3"  # Should stay on line 1

    def test_cursor_boundaries_down(self, server):
        """Test cursor down at last line"""
        server.client_cursors[1] = "2.3"
        server.clients[1] = None
        server.doc = ["hello", "world"]
        server.send_file = lambda x: None

        op = {
            "opcode": "CURSOR",
            "line": "2",
            "idx": "3",
            "char": "down",
            "ver": 0,
            "id": 1
        }

        server.process_op(op)

        assert server.client_cursors[1] == "2.3"  # Should stay on line 2

    def test_file_write_read(self, server, tmp_path):
        """Test file writing and reading"""
        test_file = tmp_path / "test_file.txt"
        server.doc = ["hello\n", "world\n", "test"]

        server.write_file(str(test_file))

        # Reset doc and read back
        server.doc = []
        server.open_file(str(test_file))

        assert server.doc == ["hello\n", "world\n", "test"]
