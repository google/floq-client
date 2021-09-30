# Copyright 2021 The Floq Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""This module provides an interface for communicating with Floq API service."""
import os
from typing import Optional
import requests

from . import errors, schemas


class ApiClient:
    """Makes HTTP requests to the Floq API service."""

    def __init__(
        self,
        hostname: str,
        api_key: str,
        version: int = 1,
        use_ssl: bool = True,
    ) -> None:
        """Creates ApiClient class instance.

        Args:
            hostname: Floq API service hostname.
            api_key: Floq API authorization key.
            version: API version.
            use_ssl: Indicates if should use HTTPS protocol.
        """
        protocol = "https" if use_ssl else "http"
        self._api_url = f"{protocol}://{hostname}/api/v{str(version)}"

        self._session = requests.Session()
        self._session.headers.update(
            {"Accept": "application/json", "X-API-Key": api_key}
        )

    def get(self, endpoint: str, stream: bool = False) -> requests.Response:
        """Sends GET request to the service.

        Args:
            endpoint: API endpoint.
            stream: Indicates if streaming response should start.

        Returns:
            `request.Response` object.
        """
        return self._make_request("get", endpoint, stream=stream)

    def post(
        self, endpoint: str, data: Optional[str] = None
    ) -> requests.Response:
        """Sends POST request to the service.

        Args:
            endpoint: API endpoint.
            data: Data to be sent to the service.

        Returns:
            `request.Response` object.
        """
        headers = {}
        if data is not None:
            headers = {
                "Content-Length": str(len(data)),
                "Content-Type": "application/json",
            }

        return self._make_request(
            "post",
            endpoint,
            data=data,
            headers=headers,
        )

    def delete(self, endpoint: str) -> requests.Response:
        """Sends DELETE request to the service.

        Args:
            endpoint: API endpoint.

        Returns:
            `request.Response` object.
        """
        return self._make_request("delete", endpoint)

    def _make_request(
        self, method: str, endpoint: str, *args, **kwargs
    ) -> requests.Response:
        """Makes API request.

        Args:
            operation: HTTP method.
            endpoint: API endpoint.

        Returns:
            `request.Response` object.

        Raises:
            ServiceError: The API returned error response.
        """
        try:
            response = self._session.request(
                method,
                os.path.join(self._api_url, endpoint),
                *args,
                timeout=30.0,
                **kwargs,
            )
            response.raise_for_status()
        except requests.HTTPError as error:
            if response.headers.get("Content-Type", None) == "application/json":
                json = response.json()
                invalid = schemas.APIErrorSchema.validate(json)
                if not invalid:
                    api_error: schemas.APIError = schemas.decode(
                        schemas.APIErrorSchema, response.text
                    )
                    message = api_error.message
                else:
                    message = json
            else:
                message = "Unknown service error"

            raise errors.ServiceError(response.status_code, message) from error

        return response
