import unittest
from pathlib import Path

from container import execute_command


class TestMain(unittest.TestCase):
    def test_always_pass(self):
        self.assertTrue(True)

    def test_execute_command_success(self):
        command = "echo Hello, World!"
        replace_dict = {}
        result = execute_command(command, replace_dict)
        self.assertIn("Hello, World!", result)

    def test_execute_command_with_replacement(self):
        command = "echo ${GREETING}"
        replace_dict = {"GREETING": "Hello, Test!"}
        result = execute_command(command, replace_dict)
        self.assertIn("Hello, Test!", result)

    def test_execute_command_with_invalid_command(self):
        command = "invalid_command"
        replace_dict = {}
        result = execute_command(command, replace_dict)
        self.assertRegex(result, r"(command not found|invalid_command: not found)")

    def test_execute_command_with_nonexistent_directory(self):
        command = "echo Hello"
        replace_dict = {}
        cwd = "/nonexistent_directory"
        result = execute_command(command, replace_dict, cwd)
        self.assertIn("Working Directory", result)

    def test_execute_command_with_valid_cwd(self):
        command = "ls"
        replace_dict = {}
        base_dir = Path(__file__).parent
        cwd = str(base_dir)
        result = execute_command(command, replace_dict, cwd)
        self.assertNotIn("Error", result)
