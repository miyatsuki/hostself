import argparse
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import tool


def exec_at(cmd: str, work_dir: Path | None = None) -> str:
    if work_dir is None:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    else:
        result = subprocess.run(
            f"cd {work_dir} && {cmd}", shell=True, capture_output=True, text=True
        )

    return result.stdout


base_dir = Path(__file__).parent.resolve()
llm = ChatAnthropic(
    model="claude-3-5-sonnet-20240620", api_key=dotenv_values()["ANTHROPIC_API_KEY"]
)


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


def main():
    parser = argparse.ArgumentParser(description="AI-assisted code modification tool")
    parser.add_argument("issue_file", help="Issue file path (for local mode)")
    parser.add_argument("--branch", help="Branch name to use or create")
    args = parser.parse_args()

    if not args.issue_file:
        print("Error: In local mode, please provide the issue file path.")
        sys.exit(1)

    # check current branch name
    if args.branch:
        new_branch_name = args.branch
    else:
        current_branch_name = exec_at("git rev-parse --abbrev-ref HEAD").strip()
        new_branch_name = (
            current_branch_name
            if current_branch_name not in ["main", "master", "develop"]
            else None
        )

    work_dir, issue_str = local_mode(args.issue_file)

    @tool
    def create_branch(branch_name: str):
        """Creates a new branch with the given name."""
        branches = exec_at("git branch --list", work_dir).split()
        if branch_name in branches:
            exec_at(f"git checkout {branch_name}", work_dir)
        else:
            exec_at(f"git checkout -b {branch_name}", work_dir)

    @tool
    def list_files() -> str:
        """Returns name of git tracked files in the repository."""
        folder_structure = exec_at("git ls-files", work_dir)
        return "\n".join(folder_structure)

    @tool
    def open_file(path: str) -> str:
        """Opens a file and returns its content."""
        try:
            with open(path, "r") as f:
                return f.read()
        except FileNotFoundError:
            return f"{path} not found."

    @tool
    def save_file(path: str, body: str) -> None:
        """Saves source files in a directory."""
        if not Path(path).parent.exists():
            Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            f.write(body)

    @tool
    def stage_file(path: str) -> None:
        """Stages a file for commit."""
        exec_at(f"git add {path}", work_dir)

    @tool
    def commit(commit_msg: str) -> None:
        """
        Finishes the execution of the chain and commits the changes.
        branch_name: feature/ai/[修正した内容] というブランチ名
        commit_msg: 日本語のコミットメッセージ。"AI: [修正した内容]" という形式で記述
        """
        exec_at(f'git commit -m "{commit_msg}"', work_dir)

    @tool
    def finish() -> None:
        """Finishes the execution of the chain."""
        exec_at(f"github .", work_dir)

    tools = [
        create_branch,
        list_files,
        open_file,
        save_file,
        stage_file,
        commit,
        finish,
    ]
    tools_dict = {tool.name: tool for tool in tools}

    query = f"""
* 以下の課題を解決できるように、既存のソースコードを修正してください
* 必要なファイルがなければ作成してください。
* 修正したファイルは指定のブランチにコミットしてください
* 修正内容を要約して教えてください
* 全て終わったらfinish()を呼び出してください

### 課題
{issue_str}

### 使用するブランチ名
{new_branch_name if new_branch_name else "新規作成"}
"""

    llm_with_tools = llm.bind_tools(tools)
    messages: list[BaseMessage] = [HumanMessage(query)]
    ai_msg = llm_with_tools.invoke(messages)

    while True or len(messages) < 20:
        print(ai_msg)
        messages.append(ai_msg)
        for tool_call in ai_msg.tool_calls:
            selected_tool = tools_dict[tool_call["name"]]
            tool_msg = selected_tool.invoke(tool_call)
            messages.append(tool_msg)

        if any([tool_call["name"] == "finish" for tool_call in ai_msg.tool_calls]):
            break

        ai_msg = llm_with_tools.invoke(messages)


if __name__ == "__main__":
    main()
