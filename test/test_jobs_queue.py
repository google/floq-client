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


class TestJobsQueueManager(unittest.TestCase):
    """Tests JobsQueueManager class behavior."""

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
        self.manager = self.container.managers.JobsQueueManager()

    def tearDown(self) -> None:
        """See base class documentation."""
        for attr in dir(self):
            if attr.startswith("mocked_"):
                getattr(self, attr).reset_mock()

    def test_flush(self) -> None:
        """Tests flush method behavior."""
        # Set up
        task = schemas.TaskSubmitted(uuid.uuid4())
        serialized_task = schemas.encode(schemas.TaskSubmittedSchema, task)

        mocked_response = unittest.mock.Mock(requests.Response)
        mocked_response.text = serialized_task

        self.mocked_client.delete.return_value = mocked_response

        # Run test
        self.manager.flush()

        # Verification
        self.mocked_client.delete.assert_called_once_with("jobs/queue")
        self.mocked_handler.open_stream.assert_called_once_with(
            f"tasks/{str(task.id)}/stream", self.manager.on_jobs_queue_flushed
        )

    def test_get(self) -> None:
        """Tests get method behavior."""
        # Set up
        queue = schemas.JobsQueue([uuid.uuid4()])

        mocked_response = unittest.mock.Mock(requests.Response)
        mocked_response.text = schemas.encode(schemas.JobsQueueSchema, queue)

        self.mocked_client.get.return_value = mocked_response

        # Run test
        response = self.manager.get()

        # Verification
        self.assertEqual(response, queue)
        self.mocked_client.get.assert_called_once_with("jobs/queue")

    def test_get_pending_job(self) -> None:
        """Tests get_pending_job method behavior."""
        # Set up
        job = schemas.PendingJob(
            uuid.uuid4(), schemas.JobStatus.IN_PROGRESS, schemas.JobType.SAMPLE
        )

        mocked_response = unittest.mock.Mock(requests.Response)
        mocked_response.text = schemas.encode(schemas.PendingJobSchema, job)

        self.mocked_client.get.return_value = mocked_response

        # Run test
        response = self.manager.get_pending_job(job.id)

        # Verification
        self.assertEqual(response, job)
        self.mocked_client.get.assert_called_once_with(
            f"jobs/queue/{str(job.id)}"
        )
