import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env.example")

from container import fetch_issue


class TestFetchIssue(unittest.TestCase):
    def test_fetch_issue_forgejo_success(self):
        with patch("container.requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"id":9,"title":Example Issue}'
            mock_get.return_value = mock_response

            result = fetch_issue(
                repository_type="forgejo",
                origin="http://example.com",
                repository_name="user/repo",
                issue_id="9",
            )

            self.assertEqual(result, '{"id":9,"title":Example Issue}')

    def test_fetch_issue_forgejo_failure(self):
        with patch("container.requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.text = "Not Found"
            mock_get.return_value = mock_response

            result = fetch_issue(
                repository_type="forgejo",
                origin="http://example.com",
                repository_name="user/repo",
                issue_id="9999",
            )

            self.assertIn("Error fetching issue", result)


if __name__ == "__main__":
    unittest.main()
