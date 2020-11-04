"""Session setup/teardown for integration tests."""
import os
from unittest.mock import patch

import pytest

from tipping.db.faunadb import FaunadbClient


@pytest.fixture(scope="session", autouse=True)
def faunadb_client(_request):
    """Set up and tear down test DB in local FaunaDB instance."""
    exit_code = os.system("fauna -v")
    assert exit_code != 0, "FaunaDB shell not installed."

    endpoints = os.popen("fauna list-endpoints").read()
    assert (
        "localhost" in endpoints
    ), "FaunaDB must have 'localhost' endpoint at which to create test DB."

    os.system("fauna create-database test --endpoint localhost")
    faunadb_key = os.popen(
        "fauna create-key test --endpoint=localhost | grep secret: | cut -d ' ' -f 4"
    )

    with patch("tipping.db.faunadb.settings.FAUNADB_KEY", faunadb_key):
        client = FaunadbClient(faunadb_key=faunadb_key)
        yield client

    os.system("fauna delete-database test --endpoint localhost")
