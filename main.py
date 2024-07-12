# %%
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# %%


# %%
# git pull
os.system(f"cd {tmp_dir} && git checkout main && git fetch -p && git pull")

# %%
contexts = ["calc.py"]

# %%
issue = "divideが0の時はraiseしてほしい。また、それを確認するようなunittestが欲しい"

# %%
codes = [(context, open(f"{tmp_dir}/{context}").read()) for context in contexts]

code_prompt = ""
for context, code in codes:
    code_prompt += f"```{context}\n"
    code_prompt += code
    code_prompt += "```\n\n"
code_prompt = code_prompt.strip()
print(code_prompt)

# %%
prompt = f"""
課題を解決するように既存のコードを修正してください。
新しいファイルが必要であれば、そのファイルを作成してください。

### 課題
{issue}

### 既存のコード
{code_prompt}
""".strip()

# %%
print(prompt)

# %%
client = OpenAI()
completion = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a smart AI programmer."},
        {"role": "user", "content": prompt},
    ],
)

print(completion.choices[0].message.content)

# %%
diff = completion.choices[0].message.content

# %%
prompt = f"""
変更後のコードと変更前のコードをマージしてください。

#### この修正で解決される課題
{issue}

#### 変更前
{code_prompt}

#### 変更後
{diff}
""".strip()

# %%
client = OpenAI()
completion = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a smart code marger."},
        {"role": "user", "content": prompt},
    ],
)

# %%
merged = completion.choices[0].message.content
print(merged)

# %%
import marvin
from pydantic import BaseModel


class File(BaseModel):
    name: str
    text: str


class PullRequest(BaseModel):
    branch_name: str
    title: str
    description: str
    files: list[File]


pr = marvin.cast(merged, target=PullRequest)

# %%
print(pr)

# %%
# clone repository under tmp dir
import os
import shutil
import tempfile

tmp_dir = tempfile.mkdtemp()
os.system(f"gh repo clone {repository_name} {tmp_dir} -- --depth=1")

# %%
# main をチェックアウト
os.system(f"cd {tmp_dir} && git checkout main")

# %%
# ブランチを作成
# ブランチ名は feature/ai/merge-code
os.system(f"cd {tmp_dir} && git checkout -b ai/{pr.branch_name}")

# %%
for file in pr.files:
    with open(os.path.join(tmp_dir, file.name), "w") as f:
        f.write(file.text)

# %%
# git add
os.system(f"cd {tmp_dir} && git add .")

# %%
# git status
os.system(f"cd {tmp_dir} && git status")

# %%
# git commit
os.system(f'cd {tmp_dir} && git commit -m "AI: {pr.title}"')

# %%
# git push
os.system(f"cd {tmp_dir} && git push origin ai/{pr.branch_name}")

# %%
pr_description = f"""
#### 解決したかった課題
{issue}

#### AIによる説明
{pr.description}
"""

# %%
# create pr
os.system(
    f"cd {tmp_dir} && gh pr create --base main --head ai/{pr.branch_name} --title '{pr.title}' --body '{pr_description}'"
)

# %%
