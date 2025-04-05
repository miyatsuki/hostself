import unittest
from unittest.mock import patch

from container import create_pull_request


class TestCreatePullRequest(unittest.TestCase):
    @patch("container.requests.post")
    def test_create_pull_request_success(self, mock_post):
        # モックの設定
        mock_post.return_value.status_code = 201
        mock_post.return_value.text = "Success"

        # テスト実行
        response = create_pull_request(
            repository_type="forgejo",
            origin="http://example.com",
            repository_name="user/repo",
            branch_name="test_branch",
            title="Test PR",
            body="This is a test pull request",
        )

        # 結果確認
        self.assertEqual(response, "Success")

    @patch("container.requests.post")
    def test_create_pull_request_failure(self, mock_post):
        # モックの設定
        mock_post.return_value.status_code = 400
        mock_post.return_value.text = "Error"

        # テスト実行
        response = create_pull_request(
            repository_type="forgejo",
            origin="http://example.com",
            repository_name="user/repo",
            branch_name="test_branch",
            title="Test PR",
            body="This is a test pull request",
        )

        # 結果確認
        self.assertEqual(response, "Error creating PR: 400 - Error")


if __name__ == "__main__":
    unittest.main()
