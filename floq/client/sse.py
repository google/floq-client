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

# pylint: disable=too-few-public-methods
"""This module provides interface for handling service events stream."""
from typing import Any, Callable, Optional, TypeVar
import marshmallow
import requests

from . import api_client, schemas


TServerSideEvent = TypeVar(
    "TServerSideEvent", bound=schemas.ServerSideEvent
)  #: :class:`floq.client.schemas.ServerSideEvent` type object


# Function to be called on receiving a new service side event
EventsListener = Callable[
    [TServerSideEvent, Optional[Any]], None
]


class EventStreamHandler:
    """Handles service streaming responses.

    Attributes:
        context (Optional[Any]): Optional context to be passed to the callback
            function.
    """

    def __init__(
        self, client: api_client.ApiClient, schema: marshmallow.Schema
    ) -> None:
        """Creates EventStreamHandler class instance.

        Args:
            client: Reference to ApiClient class object.
            schema: Schema to be used for decoding incoming event payload.
        """
        self.context: Optional[Any] = None

        self._client = client
        self._listener: Optional[EventsListener] = None
        self._schema = schema

    def open_stream(
        self, endpoint: str, listener: Optional[EventsListener] = None
    ) -> None:
        """Opens a new stream and starts processing events.

        Args:
            endpoint: API service streaming endpoint.
            listener: Optional callback function called after receiving a new
                event.
        """
        self._listener = listener
        stream_done = False

        while not stream_done:
            with self._client.get(endpoint, stream=True) as response:
                # If the stream timed out (stream_done=False), then reopen a new
                # connection. This may happen when we wait for complicated
                # simulation job results.
                stream_done = self._process_stream(response)

    def _process_stream(self, response: requests.Response) -> bool:
        """Processes streaming response.

        Decodes incoming server side events and calls the callback function
        passed to the :meth:`open_stream` method.

        The API service allows the streaming endpoints to be open only for
        certain amount of time. If the request is complete before the timeout,
        this method will return True value. Otherwise, the service will send
        the timeout event and the function will return False.

        Args:
            response: Reference to Response object.

        Returns:
            False if the stream timed out, True otherwise.
        """
        buffer = []

        for line in response.iter_lines():
            if len(line) > 0:
                buffer.append(line)
                continue

            if len(buffer) == 0:
                continue

            event_raw = "\n".join(x.decode() for x in buffer)
            try:
                event: schemas.ServerSideEvent = schemas.decode(
                    self._schema, event_raw
                )
            except marshmallow.exceptions.ValidationError:
                event: schemas.StreamTimeoutEvent = schemas.decode(
                    schemas.StreamTimeoutEventSchema, event_raw
                )

            buffer.clear()

            if isinstance(event, schemas.StreamTimeoutEvent):
                return False

            if callable(self._listener):
                self._listener(
                    event, self.context
                )  # pylint: disable=not-callable

        return True


class ExpectationJobStatusStreamHandler(EventStreamHandler):
    """Handles expectation job status event stream."""

    def __init__(self, client: api_client.ApiClient) -> None:
        """Creates ExpectationJobStatusStreamHandler class instance.

        Args:
            client: Reference to ApiClient class object.
        """
        super().__init__(client, schemas.ExpectationJobStatusEventSchema)


class SampleJobStatusStreamHandler(EventStreamHandler):
    """Handles sample job status event stream."""

    def __init__(self, client: api_client.ApiClient) -> None:
        """Creates SampleJobStatusStreamHandler class instance.

        Args:
            client: Reference to ApiClient class object.
        """
        super().__init__(client, schemas.SampleJobStatusEventSchema)


class TaskStatusStreamHandler(EventStreamHandler):
    """Handles asynchronous task status event stream."""

    def __init__(self, client: api_client.ApiClient) -> None:
        """Creates TaskStatusStream class instance.

        Args:
            client: Reference to ApiClient class object.
        """
        super().__init__(client, schemas.TaskStatusEventSchema)
