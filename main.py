import os
import shutil
import sys
import tempfile
from pathlib import Path

import marvin  # type: ignore
from dotenv import dotenv_values, load_dotenv
from openai import OpenAI
from pydantic import BaseModel

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
issue_str = os.popen(f"gh issue view {issue_no} --json title,body").read()


class Issue(BaseModel):
    title: str
    body: str
    related_files: str


issue = marvin.cast(issue_str, target=Issue)

# Read and format context files
codes = [
    (file_path, open(f"{tmp_dir}/{file_path}").read())
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
ー 新しいファイルが必要であれば、そのファイルを作成してください。
ー 可能な限り少ない変更量で課題を解決してください。課題に関係のないリファクタリングはあなたの仕事ではありません。
ー 課題に関係ない箇所は一切触らないでください。

### 課題
{issue_str}

### 既存のコード
{code_prompt}
""".strip()

# Get completion from OpenAI
completion = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "system",
            "content": "You are a smart AI programmer. You are ONLY intereseted to solve issues. You must not care about general refactoring",
        },
        {"role": "user", "content": prompt},
    ],
)

diff = completion.choices[0].message.content

# Generate merging prompt
merge_prompt = f"""
変更後のコードと変更前のコードをマージしてください。
ー 可能な限り少ない変更量でマージしてください。
ー 入力された変更点以外のリファクタリングを行ってはいけません。

#### この修正で解決される課題
{issue_str}

#### 変更前
{code_prompt}

#### 変更後
{diff}
""".strip()

# Get merged code from OpenAI
completion = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "system",
            "content": "You are a smart code merger. You ONLY care about merging code. You must not care about general refactoring.",
        },
        {"role": "user", "content": merge_prompt},
    ],
)
merged = completion.choices[0].message.content


# Pydantic models
class File(BaseModel):
    name: str
    body: str


# Parse merged code into a PullRequest object
files: list[File] = marvin.cast(merged, target=list[File])


class Diff(BaseModel):
    description: str
    commit_message: str


diff: Diff = marvin.cast(diff, target=Diff)

# Create new branch
branch_name = f"ai/fix/issue-{issue_no}"
os.system(f"cd {tmp_dir} && git checkout -b {branch_name}")

# Write files to the repository
for file in files:
    with open(os.path.join(tmp_dir, file.name), "w") as f:
        f.write(file.body)

# Git add, commit and push
os.system(f"cd {tmp_dir} && git add .")
os.system(
    f'cd {tmp_dir} && git commit -m "AI: fix #{issue_no} , {diff.commit_message}"'
)
os.system(f"cd {tmp_dir} && git push origin {branch_name}")

# PR description
pr_description = f"""
#### 解決したかった課題
{issue.title}
#{issue_no}

#### AIによる説明
{diff.description}
"""

# Create pull request
with tempfile.NamedTemporaryFile(mode="w") as f:
    f.write(pr_description)
    pr_description_file = f.name
    cmd = f"gh pr create --base main --head '{branch_name}' --title '{diff.commit_message}' --body-file {pr_description_file}"
    os.system(cmd)
