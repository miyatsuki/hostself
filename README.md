# Docker対応 AI-assisted Code Modification Tool

## tl;dr

このリポジトリは、Docker上で動作するAIを用いたコード修正ツールです。コードリポジトリの問題を自動で解析し、修正を提案・適用します。

## このリポジトリについて

このツールは、コードリポジトリの問題を自動で解析し、修正を提案・適用するAIアシスタントです。Dockerコンテナ内で実行され、問題を分析して修正コードを生成します。ForgejoおよびGitHubリポジトリでの利用に対応し、修正内容をプルリクエストとして提出することができます（現在、GitHub対応は実装中）。

## インストール方法

1. リポジトリをクローン
2. 必要な環境変数を`.env`ファイルに設定（以下の環境変数が必要）：
   - `OPENAI_API_KEY`: OpenAI APIキー
   - `GIT_USER_EMAIL`: Gitコミット用のメールアドレス
   - `GIT_USER_NAME`: Gitコミット用のユーザー名
   - `LOCAL_HOST_ALIAS`: ホストマシンのエイリアス
   - `FORGEJO_TOKEN`: Forgejo APIトークン
   - `FORGEJO_USER_NAME`: Forgejoユーザー名
   - `GH_TOKEN`: GitHub APIトークン
3. 上記の使用方法に従ってツールを実行

## 使い方

### コマンドの内容

```
python main.py <issue_str>
```

`issue_str`は解決すべき問題の説明テキストです。このテキストはAIに渡され、問題解決のためのコード修正が生成されます。

### 実行プロセス

1. Dockerイメージがビルドされます
2. コンテナが起動し、問題の解析が開始されます
3. AIが問題を分析し、必要な修正を判断します
4. コード変更が適用されます
5. 必要に応じてプルリクエストが作成されます

### サポートされている機能

- ファイルのパッチ適用
- シェルコマンドの実行
- Forgejoリポジトリへのプルリクエスト作成（GitHub対応は実装中）
- 問題の詳細取得

### 実行結果の例

```
$ python main.py "関数Xのバグを修正してください"
[Dockerイメージのビルド中...]
[コンテナを起動しています...]
[問題を分析中...]
[修正を適用中...]
[プルリクエストを作成しました: https://forgejo.example.com/user/repo/pulls/123]
```
