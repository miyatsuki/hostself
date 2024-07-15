import unittest
from pathlib import Path
from main import create_code_prompt


class TestMain(unittest.TestCase):
    def test_always_pass(self):
        self.assertTrue(True)

    def test_create_code_prompt(self):
        # テスト用のディレクトリとファイルを設定
        work_dir = Path('test_dir')
        work_dir.mkdir(exist_ok=True)
        
        file1 = work_dir / 'file1.txt'
        file1.write_text('Content of file1')
        
        file2 = work_dir / 'file2.txt'
        file2.write_text('Content of file2')
        
        selected_files = ['file1.txt', 'file2.txt']
        
        expected_output = '```file1.txt\nContent of file1```\n```file2.txt\nContent of file2```'
        
        result = create_code_prompt(selected_files, work_dir)
        
        self.assertEqual(result.strip(), expected_output)
        
        # クリーンアップ
        work_dir.rmdir()