import argparse
import json
import os
import subprocess
from pathlib import Path

import anthropic
import openai
from pydantic import BaseModel

base_dir = Path(__file__).parent

DEEPSEEK_MODEL = "deepseek-chat"

anthropic_client = anthropic.Anthropic()

# openai_client = openai.Client(api_key=env["OPENAI_API_KEY"])
openai_client = openai.Client(
    api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com"
)


argparser = argparse.ArgumentParser()
argparser.add_argument("issue_str", type=str)
args = argparser.parse_args()

issue_str = str(args.issue_str)
issue_str = issue_str.replace("http://localhost", "http://host.docker.internal")

tools = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "execute a command in a shell. Don't do sudo, since it will be executed inside docker container. ${GH_TOKEN}, ${FORGEJO_TOKEN}, ${GITLAB_TOKEN} will be replaced with the actual token.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "the command to execute",
                    },
                },
                "required": ["command"],
            },
        },
    },
]


def execute_command(command: str, replace_dict: dict[str, str] | None = None):
    if replace_dict is not None:
        for key, value in replace_dict.items():
            command = command.replace(f"${{{key}}}", value)

    # subprocessを使用して標準出力と標準エラーの両方を取得
    result = subprocess.run(command, shell=True, capture_output=True, text=True)

    # 標準出力と標準エラーを結合して返す
    output = result.stdout + "\n" + result.stderr
    return output


messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {
        "role": "user",
        "content": f"""
以下の指示を遂行してください。
遂行にあたっては現在の状態と指示の内容をまず確認し、その差分を埋めるように順番に作業してください。
作業が終わったら、本当に作業が終わっているかを確認してください。
本当に終わってたら終了の通知を出してください

#### 指示
{issue_str}
""",
    },
]


is_finished = False
while True:
    response = openai_client.chat.completions.create(
        model=DEEPSEEK_MODEL,
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
                case "execute_command":
                    arguments = json.loads(tool.function.arguments)
                    content = execute_command(
                        arguments["command"],
                        {
                            "GH_TOKEN": os.environ["GH_TOKEN"],
                            "FORGEJO_TOKEN": os.environ["FORGEJO_TOKEN"],
                            "GITLAB_TOKEN": os.environ["GITLAB_TOKEN"],
                        },
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
