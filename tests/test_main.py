import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from main import File, list_files


class TestMain(unittest.TestCase):
    def test_always_pass(self):
        self.assertTrue(True)

    def test_list_files(self):
        with TemporaryDirectory() as temp_dir:
            work_dir = Path(temp_dir)

            # Create some test files
            file1 = work_dir / "file1.txt"
            file2 = work_dir / "file2.py"
            subdir = work_dir / "subdir"
            subdir.mkdir()
            file3 = subdir / "file3.md"

            file1.write_text("Content of file1")
            file2.write_text("print('Hello, World!')")
            file3.write_text("# Markdown file")

            # Initialize git repository
            os.system(
                f"cd {work_dir} && git init && git add . && git commit -m 'Initial commit'"
            )

            # Call list_files
            files = list_files(work_dir)

            # Check if all files are listed
            self.assertEqual(len(files), 3)

            # Check if files are correctly represented
            for file in files:
                self.assertIsInstance(file, File)
                self.assertIn(
                    file.path,
                    [Path("file1.txt"), Path("file2.py"), Path("subdir/file3.md")],
                )
                self.assertEqual(file.text, (work_dir / file.path).read_text())


if __name__ == "__main__":
    unittest.main()
