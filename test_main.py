import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import os

# Add the parent directory to sys.path to import main
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from main import exec_at, local_mode, list_files, File

class TestMain(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_exec_at(self):
        result = exec_at("echo 'Hello, World!'", self.work_dir)
        self.assertEqual(result.stdout.strip(), "Hello, World!")

    def test_local_mode(self):
        issue_content = "Test issue content"
        issue_file = self.work_dir / "issue.txt"
        issue_file.write_text(issue_content)

        # Create a mock git repository
        os.mkdir(self.work_dir / ".git")

        work_dir, issue_str = local_mode(str(issue_file))
        self.assertEqual(work_dir, self.work_dir)
        self.assertEqual(issue_str, issue_content)

    def test_list_files(self):
        # Create some test files
        (self.work_dir / "file1.txt").write_text("Content 1")
        (self.work_dir / "file2.py").write_text("Content 2")

        # Mock git ls-files command
        def mock_exec_at(cmd, work_dir):
            class MockResult:
                stdout = "file1.txt\nfile2.py"
            return MockResult()

        # Patch exec_at function
        original_exec_at = exec_at
        try:
            globals()['exec_at'] = mock_exec_at
            files = list_files(self.work_dir)
            self.assertEqual(len(files), 2)
            self.assertEqual(files[0].path, Path("file1.txt"))
            self.assertEqual(files[0].text, "Content 1")
            self.assertEqual(files[1].path, Path("file2.py"))
            self.assertEqual(files[1].text, "Content 2")
        finally:
            globals()['exec_at'] = original_exec_at

if __name__ == '__main__':
    unittest.main()
