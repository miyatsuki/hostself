import os
import shutil
import sys
from pathlib import Path

import marvin
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

# Load environment variables
load_dotenv()

_, repository_name, issue = sys.argv

# Clone repository under temporary directory
tmp_dir = "tmp"
shutil.rmtree(tmp_dir, ignore_errors=True)
Path(tmp_dir).mkdir()

os.system(f"gh repo clone {repository_name} {tmp_dir} -- --depth=1")

# Checkout main branch
os.system(f"cd {tmp_dir} && git checkout main")

# Pull latest changes
os.system(f"cd {tmp_dir} && git fetch -p && git pull")

# Context files to read
contexts = ["calc.py"]  # Add more files if needed

# Issue to be fixed
issue = "divideが0の時はraiseしてほしい。また、それを確認するようなunittestが欲しい"

# Read and format context files
codes = [(context, open(f"{tmp_dir}/{context}").read()) for context in contexts]
code_prompt = ""
for context, code in codes:
    code_prompt += f"```{context}\n"
    code_prompt += code
    code_prompt += "```"

code_prompt = code_prompt.strip()
print(code_prompt)

# Generate prompt for AI
prompt = f"""
課題を解決するように既存のコードを修正してください。
新しいファイルが必要であれば、そのファイルを作成してください。

### 課題
{issue}

### 既存のコード
{code_prompt}
""".strip()

print(prompt)

# Get completion from OpenAI
client = OpenAI()
completion = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a smart AI programmer."},
        {"role": "user", "content": prompt},
    ],
)

diff = completion.choices[0].message.content
print(diff)

# Generate merging prompt
merge_prompt = f"""
変更後のコードと変更前のコードをマージしてください。

#### この修正で解決される課題
{issue}

#### 変更前
{code_prompt}

#### 変更後
{diff}
""".strip()

# Get merged code from OpenAI
completion = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a smart code marger."},
        {"role": "user", "content": merge_prompt},
    ],
)
merged = completion.choices[0].message.content
print(merged)


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

print(pr)

# Create new branch
os.system(f"cd {tmp_dir} && git checkout -b ai/{pr.branch_name}")

# Write files to the repository
for file in pr.files:
    with open(os.path.join(tmp_dir, file.name), "w") as f:
        f.write(file.text)

# Git add, commit and push
os.system(f"cd {tmp_dir} && git add .")
os.system(f'cd {tmp_dir} && git commit -m "AI: {pr.title}"')
os.system(f"cd {tmp_dir} && git push origin ai/{pr.branch_name}")

# PR description
pr_description = f"""
#### 解決したかった課題
{issue}

#### AIによる説明
{pr.description}
"""
# Create pull request
os.system(
    f"cd {tmp_dir} && gh pr create --base main --head ai/{pr.branch_name} --title '{pr.title}' --body '{pr_description}'"
)
