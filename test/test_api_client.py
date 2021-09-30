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
"""Unit test for the api_client module."""
import http
import importlib
import os
import secrets
from typing import List
import unittest
import unittest.mock
import requests

from floq.client import api_client, errors, schemas


class TestApiClient(unittest.TestCase):
    """Tests ApiClient class behavior."""

    API_KEY = secrets.token_hex(16)
    API_HOSTNAME = "localhost"
    API_PATH = "/test"

    @classmethod
    def setUpClass(cls) -> None:
        """See base class documentation."""
        cls.patchers: List[unittest.mock._patch] = []

        cls.mocked_response = unittest.mock.Mock(spec=requests.Response)

        cls.mocked_session = unittest.mock.Mock(spec=requests.Session)
        cls.mocked_session.return_value = cls.mocked_session
        cls.mocked_session.headers = {}
        cls.mocked_session.request.return_value = cls.mocked_response
        patcher = unittest.mock.patch("requests.Session", cls.mocked_session)
        cls.patchers.append(patcher)

        for patcher in cls.patchers:
            patcher.start()

        importlib.reload(api_client)

    @classmethod
    def tearDownClass(cls) -> None:
        """See base class documentation."""
        for patcher in cls.patchers:
            patcher.stop()

    def setUp(self) -> None:
        """See base class documentation."""
        self.client = api_client.ApiClient(self.API_HOSTNAME, self.API_KEY)

    def tearDown(self) -> None:
        """See base class documentation."""
        self.mocked_response.raise_for_status.side_effect = None
        for attr in dir(self):
            if attr.startswith("mocked_"):
                getattr(self, attr).reset_mock()

    def test_init(self) -> None:
        """Tests __init__ method behavior."""
        # Verify API url
        self.assertEqual(self.client._api_url, self._get_url())

        # Verify calls
        self.mocked_session.assert_called_once_with()
        self.assertEqual(
            self.mocked_session.headers,
            {"Accept": "application/json", "X-API-Key": self.API_KEY},
        )

    def test_get(self) -> None:
        """Tests get method behavior."""
        # Run test
        response = self.client.get(self.API_PATH)

        # Verification
        self.assertEqual(response, self.mocked_response)
        self.mocked_session.request.assert_called_once_with(
            "get", self._get_url(self.API_PATH), stream=False, timeout=30.0
        )

    def test_get_api_error(self) -> None:
        """Tests get method behavior: API error"""
        # Setup
        error = schemas.APIError(
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            "Server error",
        )
        serialized_error = schemas.encode(schemas.APIErrorSchema, error)

        self.mocked_response.headers = {"Content-Type": "application/json"}
        self.mocked_response.json.return_value = schemas.APIErrorSchema.dump(
            error
        )
        self.mocked_response.raise_for_status.side_effect = requests.HTTPError
        self.mocked_response.status_code = 500
        self.mocked_response.text = serialized_error

        # Run test
        with self.assertRaises(errors.ServiceError):
            self.client.get(self.API_PATH)

        # Verification
        self.mocked_session.request.assert_called_once_with(
            "get", self._get_url(self.API_PATH), stream=False, timeout=30.0
        )

    def test_get_api_invalid_error(self) -> None:
        """Tests get method behavior: not a APIError object"""
        # Setup
        self.mocked_response.headers = {"Content-Type": "application/json"}
        self.mocked_response.json.return_value = {"Incorrect": "error"}
        self.mocked_response.raise_for_status.side_effect = requests.HTTPError
        self.mocked_response.status_code = 500

        # Run test
        with self.assertRaises(errors.ServiceError):
            self.client.get(self.API_PATH)

        # Verification
        self.mocked_session.request.assert_called_once_with(
            "get", self._get_url(self.API_PATH), stream=False, timeout=30.0
        )

    def test_get_api_unknown_error(self) -> None:
        """Tests get method behavior: unknown error"""
        # Setup
        self.mocked_response.headers = {"Content-Type": "text/plain"}
        self.mocked_response.raise_for_status.side_effect = requests.HTTPError
        self.mocked_response.status_code = 500

        # Run test
        with self.assertRaises(errors.ServiceError):
            self.client.get(self.API_PATH)

        # Verification
        self.mocked_session.request.assert_called_once_with(
            "get", self._get_url(self.API_PATH), stream=False, timeout=30.0
        )

    def test_post(self) -> None:
        """Tests post method behavior."""
        test_data = '{"test": "data"}'

        # Run test
        response = self.client.post(self.API_PATH, test_data)

        # Verification
        self.assertEqual(response, self.mocked_response)
        self.mocked_session.request.assert_called_once_with(
            "post",
            self._get_url(self.API_PATH),
            data=test_data,
            headers={
                "Content-Length": str(len(test_data)),
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def test_delete(self) -> None:
        """Tests delete method behavior."""
        # Run test
        response = self.client.delete(self.API_PATH)

        # Verification
        self.assertEqual(response, self.mocked_response)
        self.mocked_session.request.assert_called_once_with(
            "delete", self._get_url(self.API_PATH), timeout=30.0
        )

    def _get_url(self, path: str = "") -> str:
        """Gets API url.

        Args:
            path: Optional endpoint path.

        Returns:
            API url.
        """
        base_url = f"https://{self.API_HOSTNAME}/api/v1"
        if path == "":
            return base_url

        return os.path.join(base_url, path)
