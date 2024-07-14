import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
import tempfile

import anthropic  # type: ignore
import marvin  # type: ignore
from dotenv import dotenv_values, load_dotenv
from miyatsuki_tools.llm import hypercast  # type: ignore
from openai import OpenAI


@dataclass(frozen=True)
class Issue:
    title: str
    body: str
    related_files: str


@dataclass(frozen=True)
class File:
    path: str
    body: str


@dataclass(frozen=True)
class Diff:
    """
    Represents a difference between two versions of a file.

    Attributes:
        summary (str): 差分の要約
        commit_message (str): 差分を一言で表すメッセージ。Conventional Commitsのフォーマットに従うこと。
    """

    summary: str
    commit_message: str


# Load environment variables
load_dotenv()
client = OpenAI()
marvin.settings.openai.api_key = dotenv_values(".env")["OPENAI_API_KEY"]


def remote_mode(issue_url):
    # https://github.com/[org_name]/[repository_name]/issues/[issue_no]
    issue_no = issue_url.split("/")[-1]
    repository_name = "/".join(issue_url.split("/")[-4:-2])

    # Clone repository under temporary directory
    script_dir = Path(__file__).parent.resolve()
    tmp_dir = script_dir / "tmp"
    if tmp_dir.exists():
        work_dir = tempfile.mkdtemp(prefix=f"{repository_name}_", dir=tmp_dir)
    else:
        work_dir = tempfile.mkdtemp(prefix=f"{repository_name}_")
    
    Path(work_dir).mkdir(parents=True)

    os.system(f"gh repo clone {repository_name} {work_dir} -- --depth=1")

    # Checkout main branch
    os.system(f"cd {work_dir} && git checkout main")

    # Pull latest changes
    os.system(f"cd {work_dir} && git fetch -p && git pull")

    # Get issue details
    issue_str = os.popen(
        f"cd {work_dir} && gh issue view {issue_no} --json title,body"
    ).read()

    return work_dir, issue_no, issue_str


def local_mode(repository, issue_no):
    script_dir = Path(__file__).parent.resolve()
    repo_path = Path(repository).resolve()
    
    if script_dir in repo_path.parents:
        work_dir = repository
    else:
        tmp_dir = script_dir / "tmp"
        work_dir = tempfile.mkdtemp(prefix=f"local_repo_", dir=tmp_dir)
        shutil.copytree(repository, work_dir, dirs_exist_ok=True)
    
    issue_file = Path(work_dir) / ".ai" / f"{issue_no}.txt"

    if not issue_file.exists():
        print(f"Error: Issue file {issue_file} not found.")
        sys.exit(1)

    with open(issue_file, "r") as f:
        issue_str = f.read()

    return work_dir, issue_no, issue_str


def main():
    parser = argparse.ArgumentParser(description="AI-assisted code modification tool")
    parser.add_argument("--remote", action="store_true", help="Run in remote mode")
    parser.add_argument(
        "repository", nargs="?", help="Repository path (for local mode)"
    )
    parser.add_argument("issue_no", nargs="?", help="Issue number (for local mode)")
    args = parser.parse_args()

    if args.remote:
        if len(sys.argv) != 3:
            print("Error: In remote mode, please provide the issue URL as an argument.")
            sys.exit(1)
        work_dir, issue_no, issue_str = remote_mode(sys.argv[2])
    else:
        if not args.repository or not args.issue_no:
            print(
                "Error: In local mode, please provide both repository path and issue number."
            )
            sys.exit(1)
        work_dir, issue_no, issue_str = local_mode(args.repository, args.issue_no)

    issue = hypercast(
        cls=Issue, input_str=issue_str, model="claude-3-5-sonnet-20240620"
    )

    # Read and format context files
    codes = [
        (file_path, open(f"{work_dir}/{file_path.strip()}").read())
        for file_path in issue.related_files.split(",")
    ]
    code_prompt = ""
    for file_path, code in codes:
        code_prompt += f"```{file_path}\n"
        code_prompt += code
        code_prompt += "```\n\n"

    code_prompt = code_prompt.strip()

    # Generate prompt for AI
    prompt = f"""
    課題を解決するように既存のコードを修正してください。
    ー 関係する部分だけを出力し、関係ない部分は省略してください
    ー 新しいファイルが必要であれば、そのファイルを作成してください。
    ー 可能な限り少ない変更量で課題を解決してください。課題に関係のないリファクタリングはあなたの仕事ではありません。
    ー 課題に関係ない箇所は一切触らないでください。

    また、修正内容の説明を示してください

    ### 課題
    {issue_str}

    ### 既存のコード
    {code_prompt}

    ### 出力フォーマット
    ```json
    {{
        "file_path": str, # 修正したファイルのフルパス
        "diff": str, # 修正後のコードの差分
        "summary": str, # 修正内容を要約したもの(日本語)
    }}[]
    ```
    """.strip()

    response = anthropic.Anthropic().messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    diff_str = response.content[0].text

    # Generate merging prompt
    merge_prompt = f"""
    変更後のコードと変更前のコードをマージしてください。
    ー コード全体を出力してください
    ー 入力された変更点以外のリファクタリングを行ってはいけません。

    #### この修正で解決される課題
    {issue_str}

    ####