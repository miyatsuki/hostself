# AI-assisted Code Modification Tool

## tl;dr

このリポジトリは、AIを用いたコード修正ツールです。コードリポジトリの問題を自動で解析し、修正を提案・適用します。

## このリポジトリについて

このツールは、コードリポジトリの問題を自動で解析し、修正を提案・適用するAIアシスタントです。ローカルモードとリモートモードの両方で動作し、問題を分析して修正コードを生成します。

## インストール方法

1. リポジトリをクローン
2. 依存関係をインストール: `pip install -r requirements.txt`
3. 必要な環境変数を`.env`ファイルに設定（OPENAI_API_KEYが必要）
4. 上記の使用方法に従ってツールを実行

## 使い方

### コマンドの内容

```
python main.py <issue_file>
```

### 実行結果の例

```
$ python main.py issue.json
Fixing issue in file main.py
Issue fixed successfully!
```