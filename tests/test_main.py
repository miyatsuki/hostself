import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from main import create_code_prompt


class TestMain(unittest.TestCase):
    def test_always_pass(self):
        self.assertTrue(True)

    def test_create_code_prompt(self):
        # テスト用のディレクトリとファイルを設定
        with TemporaryDirectory() as tmp_dir_name:
            tmp_dir = Path(tmp_dir_name)

            file1 = tmp_dir / "file1.txt"
            file1.write_text("Content of file1")

            file2 = tmp_dir / "file2.txt"
            file2.write_text("Content of file2")

            selected_files = ["file1.txt", "file2.txt"]

            expected_output = (
                "```file1.txt\nContent of file1```\n\n```file2.txt\nContent of file2```"
            )

            result = create_code_prompt(selected_files, tmp_dir)

        self.assertEqual(expected_output, result.strip())
