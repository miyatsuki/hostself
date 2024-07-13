import os
import shutil
import sys
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path

import anthropic  # type: ignore
import marvin  # type: ignore
from dotenv import dotenv_values, load_dotenv
from miyatsuki_tools.llm_openai import parse_json  # type: ignore
from openai import OpenAI

# Load environment variables
load_dotenv()
client = OpenAI()
marvin.settings.openai.api_key = dotenv_values(".env")["OPENAI_API_KEY"]

_, issue_url = sys.argv
# https://github.com/[org_name]/[repository_name]/issues/[issue_no]
issue_no = issue_url.split("/")[-1]
repository_name = "/".join(issue_url.split("/")[-4:-2])

# Clone repository under temporary directory
tmp_dir = f"tmp/{repository_name}"
shutil.rmtree(tmp_dir, ignore_errors=True)
Path(tmp_dir).mkdir(parents=True)

os.system(f"gh repo clone {repository_name} {tmp_dir} -- --depth=1")

# Checkout main branch
os.system(f"cd {tmp_dir} && git checkout main")

# Pull latest changes
os.system(f"cd {tmp_dir} && git fetch -p && git pull")

# Get issue details
issue_str = os.popen(
    f"cd {tmp_dir} && gh issue view {issue_no} --json title,body"
).read()

prompt = f"""
入力を以下のフォーマットにしてください
### 入力
{issue_str}

### フォーマット
```json
{{
    "title": str,
    "body": str,
    "related_files": str
}}
```
"""

response = anthropic.Anthropic().messages.create(
    model="claude-3-5-sonnet-20240620",
    max_tokens=1024,
    messages=[{"role": "user", "content": prompt}],
)


@dataclass(frozen=True)
class Issue:
    title: str
    body: str
    related_files: str

    @classmethod
    def from_json_str(cls, json_str: str) -> "Issue":
        return cls(**parse_json(json_str))


issue = Issue.from_json_str(response.content[0].text)


# Read and format context files
codes = [
    (file_path, open(f"{tmp_dir}/{file_path.strip()}").read())
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

#### 変更前
{code_prompt}

#### 変更後
{diff_str}

### 出力フォーマット
```json
{{
    "path": str, # ファイルのフルパス
    "body": str, # マージしたコード
}}[]
""".strip()


response = anthropic.Anthropic().messages.create(
    model="claude-3-5-sonnet-20240620",
    max_tokens=2048,
    messages=[{"role": "user", "content": merge_prompt}],
)
merged = response.content[0].text


@dataclass(frozen=True)
class File:
    path: str
    body: str


# Parse merged code into a PullRequest object
files: list[File] = marvin.cast(merged, target=list[File])


prompt = f"""
入力を以下のフォーマットにしてください
### 入力
{diff_str}

### フォーマット
```json
{{
    "summary": str, # 変更内容を要約したもの(日本語)
    "commit_message": str, # 変更内容を一行で表したコミットメッセージ(日本語)
}}
```
"""


@dataclass(frozen=True)
class Diff:
    summary: str
    commit_message: str

    @classmethod
    def from_json_str(cls, json_str: str) -> "Diff":
        return cls(**parse_json(json_str))


try:
    response = anthropic.Anthropic().messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    diff = Diff.from_json_str(response.content[0].text)
except JSONDecodeError as e:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    assert content is not None
    diff = Diff.from_json_str(content)


# Create new branch
branch_name = f"ai/fix/issue-{issue_no}"
os.system(f"cd {tmp_dir} && git checkout -b {branch_name}")

# Write files to the repository
for file in files:
    with open(os.path.join(tmp_dir, file.path), "w") as f:
        f.write(file.body)

# Git add, commit and push
os.system(f"cd {tmp_dir} && git add .")
os.system(f'cd {tmp_dir} && git commit -m "AI: fix #{issue_no}, {diff.commit_message}"')
os.system(f"cd {tmp_dir} && git push origin {branch_name}")

# PR description
pr_description = f"""
### 解決したかった課題
#{issue_no} {issue.title}

### AIによる説明
{diff.summary}
"""

# Create pull request
file_name = f"{tmp_dir}/pr_description.md"
with open(file_name, "w") as f:
    f.write(pr_description)
file_relative_path = Path(file_name).name

cmd = f"cd {tmp_dir} && gh pr create --base main --head '{branch_name}' --title '{diff.commit_message}' --body-file {file_relative_path}"
os.system(cmd)
