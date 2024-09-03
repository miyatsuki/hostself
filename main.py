import argparse
import subprocess
import tomllib
from pathlib import Path

import anthropic
import marvin
from dotenv import dotenv_values, load_dotenv
from pydantic import BaseModel

base_dir = Path(__file__).parent
load_dotenv(base_dir / ".env")
env = dotenv_values(base_dir / ".env")

marvin.settings.openai.chat.completions.model = "gpt-4o"
marvin.settings.openai.api_key = env["OPENAI_API_KEY"]
antrhopic_client = anthropic.Anthropic()


class File(BaseModel):
    path: Path
    text: str


def exec_at(cmd: str, work_dir: Path | None = None):
    if work_dir is None:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    else:
        result = subprocess.run(
            f"cd {work_dir} && {cmd}", shell=True, capture_output=True, text=True
        )

    return result


def list_files(work_dir: Path):
    """Lists the files in the repository."""
    folder_structure = exec_at("git ls-files", work_dir).stdout
    path_list = [
        Path(file) for file in folder_structure.strip().split("\n") if file.strip()
    ]

    # lock系のファイルは無視する
    path_list = [path for path in path_list if "lock" not in path.name]

    # ベクトル画像のファイルは無視する
    path_list = [path for path in path_list if path.suffix not in [".svg"]]

    # .gitignoreは無視する
    path_list = [path for path in path_list if path.name != ".gitignore"]

    config = {}
    config_path = work_dir / ".ai/config.toml"
    if config_path.exists():
        config = tomllib.loads(config_path.read_text())

    ignore_list = config.get("ignore", [])

    ans: list[File] = []
    for path in path_list:
        if str(path) not in ignore_list:
            try:
                with open(work_dir / path, "r") as f:  # ここを修正
                    ans.append(File(path=path, text=f.read()))
            except UnicodeDecodeError:
                print(f"Error: Unable to read file {path}. Skipping.")

    return ans


def fix_files(issue: str, codes: list[File]):
    prompt = f"""
入力に対して要件を満たすように修正を行います。
修正はステップバイステップで行います。どのような修正が良いかを考えてステップごとに発言してください。
最終的に修正したファイルのパスと修正後のコードを出力してください。

#### 指示
- 必要な箇所を修正してください。ただし、できるだけ修正箇所を少なくしてください。
- 修正したファイルはファイル全体を出力してください。省略は行わないでください。
- 修正したファイルについては、そのファイルのパスを出力してください。
- 修正が必要ないファイルについては返却しないでください。

#### 要件
{issue}

#### コード
{codes}

#### 出力が必要なもの
- 修正後のコード
- 修正したファイルのパス
""".strip()

    r = antrhopic_client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    files_str = r.content[0].text
    print(files_str)

    return marvin.cast(data=files_str, target=list[File])


def merge_files(files: list[File], fixed_files: list[File]):
    files_set = set(f.path for f in files)
    fixed_files_set = set(f.path for f in fixed_files)

    common_files_before = [f for f in files if f.path in fixed_files_set]
    fixed_only_files = [f for f in fixed_files if f.path not in files_set]
    common_files_after = [f for f in fixed_files if f not in fixed_only_files]

    prompt = f"""
入力に対して要件を満たすように修正を行います。
修正はステップバイステップで行い、最終的に修正後のコードを出力してください。

#### 指示
- 修正後と修正前のファイルをマージしてください。
- 修正したファイルのパスとマージ後のコードを出力してください。
- 修正前のファイルが存在しない場合、新規作成なので修正後のファイルをそのまま出力してください。
- 修正後のコードは省略されている場合があります。その箇所は修正前のコードを採用してください。
- conflictが発生した場合は、修正後の内容を採用してください。

#### 修正前のコード
{common_files_before}

#### 修正後のコード
{common_files_after}

#### 出力フォーマット
```json
{{
    "explanation": "修正の理由",
    "files": [
        {{
            "path": "ファイルのパス",
            "text": "マージ後のコード"
        }}
    ]
}}
```
""".strip()

    r = antrhopic_client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    files_str = r.content[0].text
    print(files_str)

    return marvin.cast(data=files_str, target=list[File]) + fixed_only_files


def write_files(work_dir: Path, files: list[File]):
    """Tool that writes a file to disk."""
    for file in files:
        path = work_dir / file.path
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            f.write(file.text)


def test(work_dir: Path, config: dict) -> str:
    """Runs the test suite."""
    test_result = ""
    if "tests" in config:
        for test_command in config["tests"]:
            ret = exec_at(test_command, work_dir)
            if ret.returncode != 0:
                test_result += test_command + "\n" + ret.stderr + "\n\n"

    return test_result


def main():
    parser = argparse.ArgumentParser(description="AI-assisted code modification tool")
    parser.add_argument("issue_str", help="Issue text (for local mode)")
    args = parser.parse_args()

    work_dir = Path(".")
    issue_str = args.issue_str

    config = {}
    config_path = work_dir / ".ai/config.toml"
    if config_path.exists():
        config = tomllib.loads(config_path.read_text())

    while True:
        ### open file
        files = list_files(work_dir)
        print([f.path for f in files])

        ### fix file
        fixed_files = fix_files(issue_str, files)

        ### merge
        merged_files = merge_files(files, fixed_files)

        ### write
        write_files(work_dir, merged_files)

        ### test
        test_result = test(work_dir, config)

        ### if fail continue
        if test_result:
            print(f"Test failed: {test_result}")
            issue_str = f"以下のテストが失敗しました。修正してください: {test_result}"
        else:
            print("Test passed.")
            break


if __name__ == "__main__":
    main()
