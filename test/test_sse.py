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
import abc
import typing
import uuid
import unittest
import unittest.mock
import requests
import marshmallow

from floq.client import api_client, schemas, sse


class AbstractStreamTest(unittest.TestCase, abc.ABC):
    """Base class for stream handler test."""

    event_id = uuid.uuid4()

    @classmethod
    def setUpClass(cls) -> None:
        """See base class documentation."""
        cls.mocked_response = unittest.mock.Mock(requests.Response)

        cls.mocked_ctx_manager = unittest.mock.Mock()
        cls.mocked_ctx_manager.__enter__ = unittest.mock.Mock()
        cls.mocked_ctx_manager.__enter__.return_value = cls.mocked_response
        cls.mocked_ctx_manager.__exit__ = unittest.mock.Mock()

        cls.mocked_client = unittest.mock.Mock(api_client.ApiClient)
        cls.mocked_client.get.return_value = cls.mocked_ctx_manager

        cls.mocked_listener = unittest.mock.Mock(sse.EventsListener)

        cls.handler: sse.EventStreamHandler = None

    @property
    @abc.abstractmethod
    def event(self) -> typing.Any:
        """Server side event."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def event_payload(self) -> typing.Any:
        """Server side event payload."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def event_schema(self) -> marshmallow.Schema:
        """Server side event encoding/decoding schema."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def url(self) -> str:
        """Job result endpoint."""

    def tearDown(self) -> None:
        """See base class documentation."""
        for attr in dir(self):
            if attr.startswith("mocked_"):
                getattr(self, attr).reset_mock()

    def _run_test(self) -> None:
        """Runs test."""
        # Test setup
        serialized_event = schemas.encode(self.event_schema, self.event)
        self.mocked_response.iter_lines.return_value = [
            x.encode() for x in serialized_event.split("\n")
        ]

        # Run test
        self.handler.open_stream(self.url, self.mocked_listener)

        # Verification
        self._verify_mocked_client()
        self._verify_mocked_listener(self.event)
        self._verify_mocked_response()

    def _verify_mocked_client(self) -> None:
        """Verifies calls to mocked_client mock."""
        self.mocked_client.get.assert_called_once_with(self.url, stream=True)

    def _verify_mocked_response(self) -> None:
        """Verifies calls to mocked_response mock."""
        self.mocked_response.iter_lines.assert_called_once_with()

    def _verify_mocked_listener(self, event: schemas.ServerSideEvent) -> None:
        """Verifies calls to mocked_listener mock."""
        self.mocked_listener.assert_called_once_with(event, None)


class AbstractJobStatusStreamTest(AbstractStreamTest):
    """Base class for testing AbstractJobStatusStreamHandler class behavior."""

    job_id = uuid.uuid4()


class TestExpectationJobStatusStreamHandler(AbstractJobStatusStreamTest):
    """Tests ExpectationJobStatusStreamHandler class behavior."""

    @property
    def event_payload(self) -> schemas.ExpectationJobResult:
        """See base class documentation."""
        return schemas.ExpectationJobResult(
            id=self.job_id,
            status=schemas.JobStatus.IN_PROGRESS,
            progress=schemas.JobProgress(),
        )

    @property
    def event(self) -> schemas.ExpectationJobStatusEvent:
        """See base class documentation."""
        return schemas.ExpectationJobStatusEvent(
            data=self.event_payload, id=self.event_id
        )

    @property
    def event_schema(self) -> marshmallow.Schema:
        """See base class documentation."""
        return schemas.ExpectationJobStatusEventSchema

    @property
    def url(self) -> str:
        """See base class documentation."""
        return f"jobs/exp/{str(self.job_id)}/results"

    def setUp(self) -> None:
        """See base class documentation."""
        self.handler = sse.ExpectationJobStatusStreamHandler(self.mocked_client)

    def test_open_stream(self) -> None:
        """Tests open_stream method behavior."""
        self._run_test()


class TestSampleJobStatusStreamHandler(AbstractJobStatusStreamTest):
    """Tests SampleJobStatusStreamHandler class behavior."""

    @property
    def event_payload(self) -> schemas.SampleJobResult:
        """See base class documentation."""
        return schemas.SampleJobResult(
            id=self.job_id,
            status=schemas.JobStatus.IN_PROGRESS,
            progress=schemas.JobProgress(),
        )

    @property
    def event(self) -> schemas.SampleJobStatusEvent:
        """See base class documentation."""
        return schemas.SampleJobStatusEvent(
            data=self.event_payload, id=self.event_id, timestamp=1234567890
        )

    @property
    def event_schema(self) -> marshmallow.Schema:
        """See base class documentation."""
        return schemas.SampleJobStatusEventSchema

    @property
    def url(self) -> str:
        """See base class documentation."""
        return f"jobs/sample/{str(self.job_id)}/results"

    def setUp(self) -> None:
        """See base class documentation."""
        self.handler = sse.SampleJobStatusStreamHandler(self.mocked_client)

    def test_open_stream(self) -> None:
        """Tests open_stream method behavior."""
        self._run_test()


class TestTaskStatusStreamHandler(AbstractStreamTest):
    """Tests TaskStatusStreamHandler class behavior."""

    task_id = uuid.uuid4()

    @property
    def event_payload(self) -> schemas.SampleJobResult:
        """See base class documentation."""
        return schemas.TaskStatus(schemas.TaskState.PENDING)

    @property
    def event(self) -> schemas.SampleJobStatusEvent:
        """See base class documentation."""
        return schemas.TaskStatusEvent(
            data=self.event_payload, id=self.event_id, timestamp=1234567890
        )

    @property
    def event_schema(self) -> marshmallow.Schema:
        """See base class documentation."""
        return schemas.TaskStatusEventSchema

    @property
    def url(self) -> str:
        """See base class documentation."""
        return f"jobs/sample/{str(self.task_id)}/results"

    def setUp(self) -> None:
        """See base class documentation."""
        self.handler = sse.TaskStatusStreamHandler(self.mocked_client)
        self.handler.listener = self.mocked_listener

    def test_open_stream(self) -> None:
        """Tests open_stream method behavior."""
        self._run_test()
