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
"""Unit test for the sse module."""
import uuid
import unittest
import unittest.mock
import requests

from floq.client import api_client, schemas, sse


class TestTaskStatusStreamHandler(unittest.TestCase):
    """Tests TaskStatusStreamHandler class behavior."""

    @classmethod
    def setUpClass(cls) -> None:
        """See base class documentation."""
        cls.mocked_client = unittest.mock.Mock(api_client.ApiClient)

    def setUp(self) -> None:
        """See base class documentation."""
        self.handler = sse.TaskStatusStreamHandler(self.mocked_client)

    def tearDown(self) -> None:
        """See base class documentation."""
        for attr in dir(self):
            if attr.startswith("mocked_"):
                getattr(self, attr).reset_mock()

    def test_open_stream(self) -> None:
        """Tests open_stream method behavior."""
        # Test setup
        data = schemas.TaskStatus(schemas.TaskState.PENDING)
        event = schemas.TaskStatusEvent(
            data, schemas.TaskStatusEvent.__name__, uuid.uuid4()
        )
        serialized_event = schemas.encode(schemas.TaskStatusEventSchema, event)

        mocked_response = unittest.mock.Mock(requests.Response)
        mocked_response.iter_lines.return_value = [
            x.encode() for x in serialized_event.split("\n")
        ]
        mocked_listener = unittest.mock.Mock(sse.EventsListener)

        mocked_ctx_manager = unittest.mock.Mock()
        mocked_ctx_manager.__enter__ = unittest.mock.Mock()
        mocked_ctx_manager.__enter__.return_value = mocked_response
        mocked_ctx_manager.__exit__ = unittest.mock.Mock()

        self.mocked_client.get.return_value = mocked_ctx_manager

        data = schemas.TaskSubmitted(uuid.uuid4())
        serialized_data = schemas.encode(schemas.TaskSubmittedSchema, data)

        # Run test
        self.handler.listener = mocked_listener
        self.handler.open_stream(serialized_data)

        # Verification
        self.mocked_client.get.assert_called_once_with(
            f"tasks/{str(data.id)}/stream", stream=True
        )
        mocked_response.iter_lines.assert_called_once_with()
        mocked_listener.assert_called_once_with(event, None)
