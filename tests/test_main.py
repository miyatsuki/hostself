import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from main import get_folder_structure


class TestMain(unittest.TestCase):
    def test_get_folder_structure(self):
        with TemporaryDirectory() as tmp_dir_name:
            tmp_dir = Path(tmp_dir_name)
            (tmp_dir / (".gitignore")).touch()
            with open(tmp_dir / ".gitignore", "w") as f:
                f.write("ignore_dir\n")
                f.write("dir2/child1/child_ignore.txt\n")
                f.write("*.ignore\n")

            (tmp_dir / "dir1").mkdir()
            (tmp_dir / "dir1" / "file1.txt").touch()
            (tmp_dir / "dir1" / "file2.txt").touch()
            (tmp_dir / "dir2/child1").mkdir(parents=True)
            (tmp_dir / "dir2" / "child1" / "child.txt").touch()
            (tmp_dir / "dir2" / "child1" / "child_ignore.txt").touch()
            (tmp_dir / "dir2" / "file3.txt").touch()
            (tmp_dir / "dir2" / "file4.txt").touch()
            (tmp_dir / "file5.txt").touch()
            (tmp_dir / "ignore_dir").mkdir()
            (tmp_dir / "hoge.ignore").touch()

            actual = get_folder_structure(tmp_dir)
            print(actual)

        expected = f"""\
{tmp_dir.stem}/
├── .gitignore
├── dir1/
│   ├── file1.txt
│   ├── file2.txt
├── dir2/
│   ├── child1/
│   │   ├── child.txt
│   ├── file3.txt
│   ├── file4.txt
├── file5.txt
""".strip()
        self.assertEqual(expected, actual)
