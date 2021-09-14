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
"""Unit test for the jobs_queue module."""
import uuid
import unittest
import unittest.mock
import requests

from floq.client import api_client, containers, schemas, sse


class TestWorkerManager(unittest.TestCase):
    """Tests WorkerManager class behavior."""

    @classmethod
    def setUpClass(cls) -> None:
        """See base class documentation."""
        cls.mocked_client = unittest.mock.Mock(api_client.ApiClient)
        cls.mocked_handler = unittest.mock.Mock(sse.EventStreamHandler)

        cls.container = containers.Client()
        cls.container.core.ApiClient.override(cls.mocked_client)
        cls.container.core.TaskStatusStreamHandler.override(cls.mocked_handler)

    @classmethod
    def tearDownClass(cls) -> None:
        """See base class documentation."""
        cls.container.shutdown_resources()

    def setUp(self) -> None:
        """See base class documentation."""
        self.manager = self.container.managers.WorkerManager()

    def tearDown(self) -> None:
        """See base class documentation."""
        for attr in dir(self):
            if attr.startswith("mocked_"):
                getattr(self, attr).reset_mock()

    def test_start(self) -> None:
        """Tests start method behavior."""
        self._test_worker_command("start")

    def test_status(self) -> None:
        """Tests status method behavior."""
        # Set up
        worker = schemas.Worker(schemas.WorkerState.BOOTING)

        mocked_response = unittest.mock.Mock(requests.Response)
        mocked_response.text = schemas.encode(schemas.WorkerSchema, worker)

        self.mocked_client.get.return_value = mocked_response

        # Run test
        result = self.manager.status()

        # Verification
        self.assertEqual(result, worker)
        self.mocked_client.get.assert_called_once_with("worker/status")

    def test_stop(self) -> None:
        """Tests stop method behavior."""
        self._test_worker_command("stop")

    def test_restart(self) -> None:
        """Tests restart method behavior."""
        self._test_worker_command("restart")

    def _test_worker_command(self, command: str) -> None:
        """Tests worker commands."""
        # Set up
        task = schemas.TaskSubmitted(uuid.uuid4())
        serialized_task = schemas.encode(schemas.TaskSubmittedSchema, task)

        mocked_response = unittest.mock.Mock(requests.Response)
        mocked_response.text = serialized_task

        self.mocked_client.post.return_value = mocked_response

        # Run test
        getattr(self.manager, command)()

        # Verification
        self.mocked_client.post.assert_called_once_with(f"worker/{command}")
        self.mocked_handler.open_stream.assert_called_once_with(
            f"tasks/{str(task.id)}/stream", self.manager.on_worker_command_event
        )
