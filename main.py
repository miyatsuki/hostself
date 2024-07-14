import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path

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


def exec_at(cmd: str, work_dir: Path | None = None) -> str:
    if work_dir is None:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    else:
        result = subprocess.run(
            f"cd {work_dir} && {cmd}", shell=True, capture_output=True, text=True
        )

    return result.stdout


base_dir = Path(__file__).parent.resolve()

# Load environment variables
load_dotenv(base_dir / ".env")
client = OpenAI()
marvin.settings.openai.api_key = dotenv_values(base_dir / ".env")["OPENAI_API_KEY"]


def remote_mode(issue_url: str):
    # https://github.com/[org_name]/[repository_name]/issues/[issue_no]
    issue_no = issue_url.split("/")[-1]
    repository_name = "/".join(issue_url.split("/")[-4:-2])

    # Clone repository under temporary directory
    work_dir = base_dir / f"tmp/{repository_name}"
    shutil.rmtree(work_dir, ignore_errors=True)
    Path(work_dir).mkdir(parents=True)

    exec_at(f"gh repo clone {repository_name} {work_dir} -- --depth=1")

    # Checkout main branch
    exec_at("git checkout main", work_dir)

    # Pull latest changes
    exec_at("git fetch -p && git pull", work_dir)

    # Get issue details
    issue_str = exec_at(f"gh issue view {issue_no}  --json title,body", work_dir)

    return work_dir, issue_no, issue_str


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

    return work_dir, issue_path.stem, issue_str


def main():
    parser = argparse.ArgumentParser(description="AI-assisted code modification tool")
    parser.add_argument("--remote", action="store_true", help="Run in remote mode")
    parser.add_argument(
        "issue_file", nargs="?", help="Issue file path (for local mode)"
    )
    args = parser.parse_args()

    is_remote_mode: bool = args.remote
    if is_remote_mode:
        if len(sys.argv) != 3:
            print("Error: In remote mode, please provide the issue URL as an argument.")
            sys.exit(1)
        work_dir, issue_no, issue_str = remote_mode(sys.argv[2])
    else:
        if not args.issue_file:
            print("Error: In local mode, please provide the issue file path.")
            sys.exit(1)
        work_dir, issue_no, issue_str = local_mode(args.issue_file)

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
    prompt = (Path(base_dir) / "data" / "prompt" / "modify_code.txt").read_text().format(issue_str=issue_str, code_prompt=code_prompt)

    response = anthropic.Anthropic().messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    diff_str = response.content[0].text

    # Generate merging prompt
    merge_prompt = (Path(base_dir) / "data" / "prompt" / "merge_code.txt").read_text().format(issue_str=issue_str, code_prompt=code_prompt, diff_str=diff_str)

    response = anthropic.Anthropic().messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=4096,
        messages=[{"role": "user", "content": merge_prompt}],
    )
    merged = response.content[0].text

    # Parse merged code into a PullRequest object
    files: list[File] = marvin.cast(merged, target=list[File])

    try:
        diff: Diff = hypercast(
            cls=Diff,
            input_str=diff_str,
            model="claude-3-5-sonnet-20240620",
            llm_options={"max_tokens": 2048},
        )
    except JSONDecodeError:
        diff: Diff = hypercast(cls=Diff, input_str=diff_str, model="gpt-4o")

    # Create new branch
    branch_name = f"ai/fix/issue-{issue_no}"
    exec_at(f"git checkout -b {branch_name}", work_dir)

    # Write files to the repository
    for file in files:
        if not (work_dir / file.path).parent.exists():
            (work_dir / file.path).parent.mkdir(parents=True)

        with open(work_dir / file.path, "w") as f:
            f.write(file.body)

    # Git add, commit and push
    exec_at(f"git add .", work_dir)

    if is_remote_mode:
        commit_message = f"AI: fix #{issue_no}, {diff.commit_message}"
    else:
        commit_message = f"AI: {diff.commit_message}"
    exec_at(f'git commit -m "{commit_message}"', work_dir)

    if is_remote_mode:
        exec_at(f"git push origin {branch_name}", work_dir)

        # PR description
        pr_description = f"""
        ### 解決したかった課題
        #{issue_no} {issue.title}

        ### AIによる説明
        {diff.summary}
        """

        # Create pull request
        file_name = f"{work_dir}/pr_description.md"
        with open(file_name, "w") as f:
            f.write(pr_description)
        file_relative_path = Path(file_name).name

        cmd = f"gh pr create --base main --head '{branch_name}' --title '{diff.commit_message}' --body-file {file_relative_path}"
        exec_at(cmd, work_dir)


if __name__ == "__main__":
    main()