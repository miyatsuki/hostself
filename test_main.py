import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from main import exec_at, local_mode, list_files, fix_files, merge_files, write_files, stage_file, checkout, commit_files, test

class TestMain(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_exec_at(self):
        result = exec_at("echo 'test'", self.work_dir)
        self.assertEqual(result.stdout.strip(), 'test')

    def test_local_mode(self):
        issue_file = self.work_dir / "issue.txt"
        issue_file.write_text("Test issue")
        work_dir, issue_str = local_mode(str(issue_file))
        self.assertEqual(issue_str, "Test issue")

    def test_list_files(self):
        test_file = self.work_dir / "test.txt"
        test_file.write_text("Test content")
        files = list_files(self.work_dir)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].path, Path("test.txt"))
        self.assertEqual(files[0].text, "Test content")

    def test_fix_files(self):
        issue = "Fix typo in greeting"
        codes = [File(path=Path("test.py"), text="print('Hello, wrold!')")]
        fixed_files, _ = fix_files(issue, codes)
        self.assertEqual(fixed_files[0].text, "print('Hello, world!')")

    def test_merge_files(self):
        original = [File(path=Path("test.py"), text="print('Hello, world!')")]
        fixed = [File(path=Path("test.py"), text="print('Hello, World!')")]
        merged, _ = merge_files(original, fixed)
        self.assertEqual(merged[0].text, "print('Hello, World!')")

    def test_write_files(self):
        files = [File(path=Path("test.txt"), text="Test content")]
        write_files(self.work_dir, files)
        self.assertTrue((self.work_dir / "test.txt").exists())
        self.assertEqual((self.work_dir / "test.txt").read_text(), "Test content")

    def test_stage_file(self):
        test_file = self.work_dir / "test.txt"
        test_file.write_text("Test content")
        exec_at("git init", self.work_dir)
        files = [File(path=Path("test.txt"), text="Test content")]
        stage_file(self.work_dir, files)
        result = exec_at("git status --porcelain", self.work_dir)
        self.assertIn("A  test.txt", result.stdout)

    def test_checkout(self):
        exec_at("git init", self.work_dir)
        checkout(self.work_dir, "test-branch")
        result = exec_at("git branch --show-current", self.work_dir)
        self.assertEqual(result.stdout.strip(), "test-branch")

    def test_commit_files(self):
        exec_at("git init", self.work_dir)
        exec_at("git config user.email 'test@example.com'", self.work_dir)
        exec_at("git config user.name 'Test User'", self.work_dir)
        files = [File(path=Path("test.txt"), text="Test content")]
        write_files(self.work_dir, files)
        stage_file(self.work_dir, files)
        branch_name = commit_files(self.work_dir, files, "Fix issue", "Merge changes", None)
        self.assertIsNotNone(branch_name)
        result = exec_at("git log -1 --pretty=%B", self.work_dir)
        self.assertIn("AI:", result.stdout)

    def test_test(self):
        config = {"tests": ["echo 'Running tests'"]}
        result = test(self.work_dir, config)
        self.assertEqual(result, "")

if __name__ == '__main__':
    unittest.main()
