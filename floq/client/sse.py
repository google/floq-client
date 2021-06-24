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
"""This module provides classes for handling Floq API service events stream."""
import abc
from typing import Any, Callable, Optional, TypeVar
import marshmallow
import requests

from . import api_client, schemas


TServerSideEvent = TypeVar("TServerSideEvent", bound=schemas.ServerSideEvent)


# Function to be called on receiving a new ServerSideEvent
EventsListener = Callable[
    [TServerSideEvent, Optional[Any]],
    None,
]


class AbstractEventStreamHandler(
    abc.ABC
):  # pylint: disable=too-few-public-methods
    """Abstract class handling service streaming responses.

    Attributes:
        listener: Callback function to be invoked on receiving a new event.
        context: Optional context to be passed to the callback function.
    """

    def __init__(
        self, client: api_client.ApiClient, schema: marshmallow.Schema
    ) -> None:
        """Creates AbstractEventStreamHandler class instance.

        Args:
            client: Reference to ApiClient class object.
            schema: Schema to be used for decoding incoming event payload.
        """
        self.context: Optional[Any] = None
        self.listener: Optional[EventsListener] = None

        self._client = client
        self._schema = schema

    @abc.abstractmethod
    def open_stream(self, *args, **kwargs) -> None:
        """Opens a new stream and starts processing events."""

    def _process_stream(self, response: requests.Response) -> None:
        """Processes streaming response.

        Args:
            response: Reference to Response object.
        """
        buffer = []
        for line in response.iter_lines():
            if len(line) > 0:
                buffer.append(line)
                continue

            if len(buffer) == 0:
                continue

            event_raw = "\n".join(x.decode() for x in buffer)
            event: schemas.ServerSideEvent = schemas.decode(
                self._schema, event_raw
            )
            if self.listener and callable(self.listener):
                self.listener(  # pylint: disable=not-callable
                    event, self.context
                )

            buffer.clear()


class TaskStatusStreamHandler(
    AbstractEventStreamHandler
):  # pylint: disable=too-few-public-methods
    """Handles asynchronous task status event stream."""

    def __init__(self, client: api_client.ApiClient) -> None:
        """Creates TaskStatusStream class instance.

        Args:
            client: Reference to ApiClient class object.
        """
        super().__init__(client, schemas.TaskStatusEventSchema)

    def open_stream(self, content: str) -> None:
        """Opens a new stream and starts processing events.

        Args:
            content: JSON encoded TaskSubmitted object.
        """
        task: schemas.TaskSubmitted = schemas.decode(
            schemas.TaskSubmittedSchema, content
        )
        with self._client.get(
            f"tasks/{str(task.id)}/stream", stream=True
        ) as response:
            self._process_stream(response)
