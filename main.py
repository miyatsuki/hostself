import argparse
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import anthropic
import marvin
from dotenv import dotenv_values, load_dotenv
from pydantic import BaseModel

load_dotenv()

marvin.settings.openai.chat.completions.model = "gpt-4o"
antrhopic_client = anthropic.Anthropic()


class File(BaseModel):
    path: Path
    text: str


class Commit(BaseModel):
    message: str
    branch: str | None


def exec_at(cmd: str, work_dir: Path | None = None):
    if work_dir is None:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    else:
        result = subprocess.run(
            f"cd {work_dir} && {cmd}", shell=True, capture_output=True, text=True
        )

    return result


def local_mode(issue_file: str):
    issue_path = Path(issue_file).resolve()
    assert issue_path.exists(), f"Error: Issue file {issue_path} not found."

    # Find git repository root
    work_dir = issue_path.parent
    while not (work_dir / ".git").exists():
        work_dir = work_dir.parent
        if work_dir == work_dir.parent:  # Reached root directory
            print(f"Error: Git repository not found for {issue_file}")
            sys.exit(1)

    with open(issue_path, "r") as f:
        issue_str = f.read()

    return work_dir, issue_str


def list_files(work_dir: Path):
    """Lists the files in the repository."""
    folder_structure = exec_at("git ls-files", work_dir).stdout
    path_list = [
        Path(file) for file in folder_structure.strip().split("\n") if file.strip()
    ]

    ans: list[File] = []
    for path in path_list:
        with open(path, "r") as f:
            ans.append(File(path=path, text=f.read()))

    return ans


def fix_files(issue: str, codes: list[File]):
    prompt = f"""
入力に対して要件を満たすように修正を行います。

#### 指示
- 修正が必要な箇所を修正してください。
- 修正したファイルはファイル全体を出力してください。省略は行わないでください。
- 修正が必要ないファイルについては返却しないでください。

#### 要件
{issue}

#### コード
{codes}
""".strip()

    r = antrhopic_client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    files_str = r.content[0].text
    print(files_str)

    return marvin.cast(data=files_str, target=list[File]), files_str


def merge_files(files: list[File], fixed_files: list[File]):
    files_set = set(f.path for f in files)
    fixed_files_set = set(f.path for f in fixed_files)

    common_files_before = [f for f in files if f.path in fixed_files_set]
    fixed_only_files = [f for f in fixed_files if f.path not in files_set]
    common_files_after = [f for f in fixed_files if f not in fixed_only_files]

    prompt = f"""
入力に対して要件を満たすように修正を行います。

#### 指示
- 修正後と修正前のファイルをマージしてください。
- 修正後がコード全体でない場合、修正前の内容と辻褄を合わせてマージしてください
- conflictが発生した場合は、修正後の内容を採用してください。

#### 修正前のコード
{common_files_before}

#### 修正後のコード
{common_files_after}
""".strip()

    r = antrhopic_client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    files_str = r.content[0].text
    print(files_str)

    return marvin.cast(data=files_str, target=list[File]) + fixed_only_files, files_str


def write_files(work_dir: Path, files: list[File]):
    """Tool that writes a file to disk."""
    for file in files:
        path = work_dir / file.path
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            f.write(file.text)


def stage_file(work_dir: Path, files: list[File]):
    """Stages a file for commit."""
    for file in files:
        exec_at(f"git add {file.path}", work_dir)


def checkout(work_dir: Path, branch_name: str | None):
    """Creates a new branch with the given name."""
    branches = exec_at("git branch --list", work_dir).stdout.split()
    if branch_name in branches:
        exec_at(f"git checkout {branch_name}", work_dir)
    else:
        exec_at(f"git checkout -b {branch_name}", work_dir)


def commit_files(
    work_dir: Path,
    files: list[File],
    issue_str: str,
    merge_str: str,
    branch_name: str | None,
):
    prompt = f"""
以下のような修正を行います
コミットメッセージとブランチ名を考えてください

#### 修正時のコメント
{issue_str}

#### マージ時のコメント
{merge_str}

#### 修正後のコード
{files}
""".strip()

    r = antrhopic_client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    files_str = r.content[0].text
    commit_msg = marvin.cast(data=files_str, target=Commit)

    if branch_name is None:
        checkout(work_dir, commit_msg.branch)
    else:
        checkout(work_dir, branch_name)

    write_files(work_dir, files)
    stage_file(work_dir, files)
    exec_at(f'git commit -m "AI: {commit_msg.message}"', work_dir)
    return commit_msg.branch


def test(work_dir: Path, config: dict) -> str:
    """Runs the test suite."""
    test_result = ""
    if "tests" in config:
        for test_command in config["tests"]:
            ret = exec_at(test_command, work_dir)
            if ret.returncode != 0:
                test_result += ret.stderr

    return test_result


def main():
    parser = argparse.ArgumentParser(description="AI-assisted code modification tool")
    parser.add_argument("issue_file", help="Issue file path (for local mode)")
    args = parser.parse_args()

    if not args.issue_file:
        print("Error: In local mode, please provide the issue file path.")
        sys.exit(1)

    current_branch_name = exec_at("git rev-parse --abbrev-ref HEAD").stdout
    branch_name = (
        None
        if current_branch_name in ["main", "master", "develop"]
        else current_branch_name
    )
    work_dir, issue_str = local_mode(args.issue_file)

    config = {}
    config_path = work_dir / ".ai/config.toml"
    if config_path.exists():
        config = tomllib.loads(config_path.read_text())

    while True:
        ### open file
        files = list_files(work_dir)

        ### fix file
        fixed_files, fix_comments = fix_files(issue_str, files)

        ### merge
        merged_files, merge_comments = merge_files(files, fixed_files)

        ### commit
        branch_name = commit_files(
            work_dir, merged_files, fix_comments, merge_comments, branch_name
        )

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
