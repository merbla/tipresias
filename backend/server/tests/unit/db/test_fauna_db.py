# pylint: disable=missing-docstring

from unittest import TestCase
from unittest.mock import patch

from server.db.fauna_db import FaunaDBClient


class TestFaunaDBClient(TestCase):
    @patch("server.db.fauna_db.requests.post")
    def test_import(self, mock_post):
        FaunaDBClient.import_schema()

        # It posts schema to FaunaDB
        mock_post.assert_called()
