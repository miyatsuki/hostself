import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Literal

import openai
import requests

base_dir = Path(__file__).parent

OPENAI_MODEL = "gpt-4o-2024-11-20"
# DEEPSEEK_MODEL = "deepseek-reasoning"

# openai_client = openai.Client(api_key=env["OPENAI_API_KEY"])
openai_client = openai.Client(
    api_key=os.getenv("OPENAI_API_KEY", ""),
    # base_url="https://api.deepseek.com"
)


def execute_command(command: str, replace_dict: dict[str, str], cwd: str | None = None):
    for key, value in replace_dict.items():
        command = command.replace(f"${{{key}}}", value)

    try:
        if cwd:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, cwd=cwd
            )
        else:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)

        # 標準出力と標準エラーを結合して返す
        output = result.stdout + "\n" + result.stderr
        return output
    except subprocess.CalledProcessError as e:
        return f"Error executing command:\n{e}"
    except FileNotFoundError as e:
        return f"Working Directory {cwd} does not exist:\n{e}"
    except Exception as e:
        return f"Error executing command:\n{e}"


def fetch_issue(
    repository_type: Literal["github", "forgejo"],
    origin: str,
    repository_name: str,
    issue_id: str,
):
    match repository_type:
        case "github":
            # Not Implemented Yet
            raise NotImplementedError("GitHub is not implemented yet")
        case "forgejo":
            FORGEJO_PAT = os.environ["FORGEJO_TOKEN"]

            # リクエストヘッダーの設定
            headers = {"Authorization": f"token {FORGEJO_PAT}"}

            # APIエンドポイントURL
            url = f"{origin}/api/v1/repos/{repository_name}/issues/{issue_id}"

            # GETリクエストを送信
            response = requests.get(url, headers=headers)

            # レスポンスをチェック
            if response.status_code == 200:
                return response.text
            else:
                return f"Error fetching issue: {response.status_code} - {response.text}"
        case _:
            raise ValueError(f"Unknown repository type {repository_type}")


def patch_file(file_path: str, patch: str):
    """
    ファイルをパッチする
    params:
        file_path: パッチを適用するファイルのパス
        patch: 適用するパッチ。unified diff形式
    returns:
        適用後のファイルの内容
    """

    # パッチを適用する
    try:
        result = subprocess.run(
            f"patch {file_path}",
            input=patch,
            shell=True,
            capture_output=True,
            text=True,
        )

        # 標準出力と標準エラーを結合して返す
        output = result.stdout + "\n" + result.stderr
        return output
    except subprocess.CalledProcessError as e:
        return f"Error patching file:\n{e}"
    except FileNotFoundError as e:
        return f"File {file_path} does not exist:\n{e}"
    except Exception as e:
        return f"Error patching file:\n{e}"


def create_pull_request(
    repository_type: Literal["github", "forgejo"],
    origin: str,
    repository_name: str,
    branch_name: str,
    title: str,
    body: str,
):
    FORGEJO_USER_NAME = os.environ["FORGEJO_USER_NAME"]
    match repository_type:
        case "github":
            # Not Implemented Yet
            raise NotImplementedError("GitHub is not implemented yet")
        case "forgejo":
            FORGEJO_PAT = os.environ["FORGEJO_TOKEN"]

            # リクエストヘッダーの設定
            headers = {
                "Authorization": f"token {FORGEJO_PAT}",
                "Content-Type": "application/json",
            }

            # リクエストボディの設定
            payload = {
                "base": "main",
                "head": f"{FORGEJO_USER_NAME}:{branch_name}",
                "title": title,
                "body": body,
            }

            # APIエンドポイントURL
            url = f"{origin}/api/v1/repos/{repository_name}/pulls"

            # POSTリクエストを送信
            response = requests.post(url, headers=headers, json=payload)

            # レスポンスをチェック
            if response.status_code >= 200 and response.status_code < 300:
                return response.text
            else:
                return f"Error creating PR: {response.status_code} - {response.text}"
        case _:
            raise ValueError(f"Unknown repository type {repository_type}")


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument("issue_str", type=str)
    args = argparser.parse_args()

    issue_str = str(args.issue_str)

    tools = [
        {
            "type": "function",
            "function": {
                "name": "fetch_issue",
                "description": "fetch the issue from the given url",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repository_type": {
                            "type": "string",
                            "description": "the type of the repository",
                            "enum": ["github", "forgejo"],
                        },
                        "origin": {
                            "type": "string",
                            "description": "the origin of the Issue URL. e.g. https://github.com, https://host.docker.internal:3000",
                        },
                        "repository_name": {
                            "type": "string",
                            "description": "the repository name. e.g. owner/repo",
                        },
                        "issue_id": {
                            "type": "string",
                            "description": "the issue id",
                        },
                    },
                    "required": [
                        "repository_type",
                        "origin",
                        "repository_name",
                        "issue_id",
                    ],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "patch_file",
                "description": "patch the file with the given unified diff patch. returns the patched file content",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "the path to the file to patch",
                        },
                        "patch": {
                            "type": "string",
                            "description": "the patch to apply. unified diff format",
                        },
                    },
                    "required": ["file_path", "patch"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "execute_command",
                "description": """
execute a command in a shell.
* Don't do sudo, since it will be executed inside docker container.
* use cwd parameter instead of cd command, since it will be executed in a new shell.
* ${GH_TOKEN}, ${FORGEJO_TOKEN}, ${GITLAB_TOKEN} will be replaced with the actual token.
    * they are corresponding to GitHub, ForgeJo, and GitLab tokens.
    * so, when you want to push to GitHub, you can use https url with ${GH_TOKEN}
    """.strip(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "the command to execute",
                        },
                        "cwd": {
                            "type": "string",
                            "description": "the working directory",
                        },
                    },
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_pull_request",
                "description": "create a pull request",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repository_type": {
                            "type": "string",
                            "description": "the type of the repository",
                            "enum": ["github", "forgejo"],
                        },
                        "origin": {
                            "type": "string",
                            "description": "the origin of the Issue URL. e.g. https://github.com, https://host.docker.internal:3000",
                        },
                        "repository_name": {
                            "type": "string",
                            "description": "the repository name. e.g. owner/repo",
                        },
                        "branch_name": {
                            "type": "string",
                            "description": "the branch name",
                        },
                        "title": {
                            "type": "string",
                            "description": "the title of the pull request",
                        },
                        "body": {
                            "type": "string",
                            "description": "the body of the pull request",
                        },
                    },
                    "required": [
                        "repository_type",
                        "origin",
                        "repository_name",
                        "branch_name",
                        "title",
                        "body",
                    ],
                },
            },
        },
    ]

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": f"""
以下の指示を遂行してください。
遂行にあたっては現在の状態と指示の内容をまず確認し、その差分を埋めるように順番に作業してください。
作業が終わったら、本当に作業が終わっているかを確認してください。作業が終わっているかの確認とは最低でも以下の2点が担保されていることを指します。状況に応じて他に確認すべきことがあればそれも併せて実行してください。
    * 改めて指示文の内容を読んで、現在の状態と指示の内容の間の差分がないか振り返ること
    * 修正の量が最小限であるかを見直すこと
    * unittestがある場合はそれを実行して全てパスすること
本当に終わってたら終了の通知を出してください

* 全てのコマンドはdocker上で動いているpythonのsubprocess.run()で実行されます。そのため、cdは使わないでください
* urlが与えられた場合はまずそのurlを開いてください
* issueに対応するためのブランチが必要な場合、新しく作ってください
* コミットする際は[AI]というプレフィックスをつけ、その後にconventional commitの形式でコミットメッセージを書いてください
    * 例: [AI] feat: add new feature

#### 指示
{issue_str}
    """,
        },
    ]

    is_finished = False
    while True:
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=tools,
        )
        print(response)

        if is_finished:
            break

        message = response.choices[0].message
        messages.append(message)

        if message.tool_calls is not None:
            for tool in message.tool_calls:
                print(tool, flush=True)

                name = tool.function.name
                match name:
                    case "fetch_issue":
                        arguments = json.loads(tool.function.arguments)
                        content = fetch_issue(
                            arguments["repository_type"],
                            arguments["origin"],
                            arguments["repository_name"],
                            arguments["issue_id"],
                        )
                    case "patch_file":
                        arguments = json.loads(tool.function.arguments)
                        content = patch_file(
                            arguments["file_path"],
                            arguments["patch"],
                        )
                    case "execute_command":
                        arguments = json.loads(tool.function.arguments)
                        content = execute_command(
                            arguments["command"],
                            {
                                "GH_TOKEN": os.environ["GH_TOKEN"],
                                "FORGEJO_TOKEN": os.environ["FORGEJO_TOKEN"],
                            },
                            arguments.get("cwd"),
                        )
                    case "create_pull_request":
                        arguments = json.loads(tool.function.arguments)
                        content = create_pull_request(
                            arguments["repository_type"],
                            arguments["origin"],
                            arguments["repository_name"],
                            arguments["branch_name"],
                            arguments["title"],
                            arguments["body"],
                        )
                    case "notify_finished":
                        arguments = json.loads(tool.function.arguments)
                        content = arguments["message"]
                        is_finished = True
                    case _:
                        raise ValueError(f"Unknown tool {name}")

                messages.append(
                    {"role": "tool", "tool_call_id": tool.id, "content": content}
                )
                print(content, flush=True)
        else:
            print(message.content, flush=True)

        if response.choices[0].finish_reason == "stop":
            break
