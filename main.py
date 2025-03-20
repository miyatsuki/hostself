import argparse
import subprocess
import uuid
from pathlib import Path

from dotenv import dotenv_values

base_dir = Path(__file__).parent
env = dotenv_values(base_dir / ".env")
LOCAL_HOST_ALIAS = env["LOCAL_HOST_ALIAS"]


def main():
    parser = argparse.ArgumentParser(description="AI-assisted code modification tool")
    parser.add_argument("issue_str", help="Issue text (for local mode)")
    parser.add_argument(
        "--log-dir", help="Directory to store Docker execution logs", default="logs"
    )
    args = parser.parse_args()

    issue_str = args.issue_str

    # ユニークなコンテナ名を生成
    container_name = f"hostself-container-{uuid.uuid4().hex[:8]}"

    try:
        subprocess.run(
            [
                "docker",
                "build",
                "-t",
                "hostself",
                str(base_dir),
                "--build-arg",
                f"GIT_USER_EMAIL={env['GIT_USER_EMAIL']}",
                "--build-arg",
                f"GIT_USER_NAME={env['GIT_USER_NAME']}",
            ]
        )

        # コンテナを作成して起動する（1コマンドで実行）
        # --rmオプションを追加してコンテナ終了時に自動削除するようにする
        # .envファイルの内容を環境変数として渡す
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",  # コンテナ終了時に自動削除
                "--env-file",
                str(base_dir / ".env"),  # .envファイルの内容を環境変数として渡す
                "--name",
                container_name,
                "--add-host",
                f"{LOCAL_HOST_ALIAS}:host-gateway",
                "hostself",  # イメージ名
                "python",
                "container.py",
                issue_str,
            ],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"エラーが発生しました: {e}")
        subprocess.run(["docker", "rm", "-f", container_name], check=True)


if __name__ == "__main__":
    main()
