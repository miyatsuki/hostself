import os
import shutil
import sys
import tempfile
from pathlib import Path

import marvin
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
tmp_dir = "tmp"
shutil.rmtree(tmp_dir, ignore_errors=True)
Path(tmp_dir).mkdir()

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
    code_prompt += "```
"

code_prompt = code_prompt.strip()

# Generate prompt for AI
prompt = f"""
課題を解決するように既存のコードを修正してください。
新しいファイルが必要であれば、そのファイルを作成してください。

### 課題
{issue_str}

### 既存のコード
{code_prompt}
""".strip()

# Get completion from OpenAI
completion = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a smart AI programmer."},
        {"role": "user", "content": prompt},
    ],
)

diff = completion.choices[0].message.content

# Generate merging prompt
merge_prompt = f"""
変更後のコードと変更前のコードをマージしてください。

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
        {"role": "system", "content": "You are a smart code merger."},
        {"role": "user", "content": merge_prompt},
    ],
)
merged = completion.choices[0].message.content


# Pydantic models
class File(BaseModel):
    name: str
    text: str


class PullRequest(BaseModel):
    branch_name: str
    title: str
    description: str
    files: list[File]


# Parse merged code into a PullRequest object
pr = marvin.cast(merged, target=PullRequest)

# Create new branch
os.system(f"cd {tmp_dir} && git checkout -b ai/{pr.branch_name}")

# Write files to the repository
for file in pr.files:
    with open(os.path.join(tmp_dir, file.name), "w") as f:
        f.write(file.text)

# Git add, commit and push
os.system(f"cd {tmp_dir} && git add .")
os.system(f'cd {tmp_dir} && git commit -m "AI: {pr.title}"")
os.system(f"cd {tmp_dir} && git push origin ai/{pr.branch_name}")

# PR description
pr_description = f"""
#### 解決したかった課題
{issue.title}

#### AIによる説明
{pr.description}
"""

# Create pull request
with tempfile.NamedTemporaryFile(mode="w") as f:
    f.write(pr_description)
    pr_description_file = f.name
    cmd = f"gh pr create --base main --head 'ai/{pr.branch_name}' --title '{pr.title}' --body-file {pr_description_file}"

os.system(cmd)
