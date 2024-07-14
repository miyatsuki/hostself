# AI-assisted Code Modification Tool

## About

This tool is an AI-assisted code modification utility that helps automate the process of fixing issues in code repositories. It can work in both local and remote modes, analyzing issues and generating code changes to address them.

## Usage

### Remote Mode

```
python main.py --remote <issue_url>
```

### Local Mode

```
python main.py <issue_file>
```

## Installation

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables in a `.env` file (OPENAI_API_KEY required)
4. Run the tool using the usage instructions above