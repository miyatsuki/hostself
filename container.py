import argparse
import os
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

response = openai_client.chat.completions.create(
    model=DEEPSEEK_MODEL,
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": issue_str},
    ],
)

response_text = response.choices[0].message.content
print(response_text)
