"""Module for all FaunaDB functionality."""

from typing import Literal, Union
import os

import requests
from django.conf import settings

ImportMode = Union[Literal["merge"], Literal["overwrite"]]

FAUNA_DB_DOMAIN = (
    "https://graphql.fauna.com"
    if settings.ENVIRONMENT == "production"
    else "http://localhost:8084"
)


class FaunaDBClient:
    """API client for calling FaunaDB endpoints."""

    @classmethod
    def import_schema(cls, mode: ImportMode = "merge"):
        """Import a GQL schema.

        Params:
        -------
        mode: how to update the GQL schema. Accepts "merge" to update existing schema
            or "overwrite" to replace it.
        """
        url = f"#{FAUNA_DB_DOMAIN}/import?mode={mode}"
        schema_filepath = os.path.join(settings.BASE_DIR, "server/db/schema.gql")

        with open(schema_filepath, "rb") as f:
            schema_file = f.read()

        requests.post(url, data=schema_file)
