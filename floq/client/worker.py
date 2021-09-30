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
"""This module provides interface for managing remote TPU worker."""
import enum
import threading
from typing import Optional

from . import api_client, schemas, sse


class WorkerManager:
    """Manages remote TPU worker.

    The Floq service does not handle worker commands immediately, but schedules
    the request for execution and starts emitting events along with run
    progress. Thus, when calling start, stop or restart method the manager
    sends the request to the Floq service and opens an event stream connection.
    Every time a new message is received, the :meth:`on_worker_command_event`
    callback method is called and prints an output message once the execution is
    done.

    All TPU worker commands are executed synchronously by default. It means the
    further code execution will be blocked until the Floq service sends an event
    with :attr:`floq.client.schemas.TaskState.DONE` status. Optionally the
    request can be executed asynchronously (in a separate thread) by passing
    `async_request=True` argument to the corresponding methods.
    """

    class Command(enum.IntEnum):
        """TPU worker command."""

        RESTART = enum.auto()  #: Restarts TPU worker
        START = enum.auto()  #: Starts TPU worker
        STOP = enum.auto()  #: Stops TPU worker

    def __init__(
        self,
        client: api_client.ApiClient,
        handler: sse.EventStreamHandler,
    ) -> None:
        """Creates WorkerManager class instance.

        Args:
            client: Reference to ApiClient object.
            handler: Reference to EventStreamHandler type object.
        """
        self._client = client
        self._handler = handler

    def on_worker_command_event(  # pylint: disable=no-self-use
        self, event: schemas.TaskStatusEvent, context: Optional[Command]
    ) -> None:
        """Callback function triggered after receiving a worker command
        progress event.

        Args:
            event: Received event.
            context: Optional user context data passed together with the
                event.
        """
        if context is None:
            raise RuntimeError("Missing worker command context")

        verb = context.name.capitalize()
        if event.data.state == schemas.TaskState.PENDING:
            print(f"{verb} TPU worker scheduled for execution")
            return

        if event.data.state == schemas.TaskState.RUNNING:
            suffix = (
                f"{'p' if context == WorkerManager.Command.STOP else ''}ing"
            )
            verb = f"{verb}{suffix}"
            print(f"{verb} TPU worker...")
            return

        if event.data.success:
            suffix = f"{'p' if context == WorkerManager.Command.STOP else ''}ed"
            verb = f"{verb}{suffix}"
            print(f"{verb} TPU worker")
        else:
            print(
                f"Failed to {context.name.lower()} worker: {event.data.error}"
            )

    def restart(
        self, async_request: bool = False
    ) -> Optional[threading.Thread]:
        """Restarts worker.

        This method makes synchronous request to the Floq API service, thus it
        will block code execution until the TPU worker is up and running. To
        make it asynchronous, pass `async_request=True`.

        Args:
            async_request: Indicates if the request should be executed
                asynchronously.

        Returns:
            `threading.Thread` object handle if the `async_request` argument
            True, `None` otherwise.
        """
        return self._send_worker_command(
            WorkerManager.Command.RESTART, async_request
        )

    def start(self, async_request: bool = False) -> Optional[threading.Thread]:
        """Starts worker.

        This method makes synchronous request to the Floq API service, thus it
        will block code execution until the TPU worker is up and running. To
        make it asynchronous, pass async_request=True.

        Args:
            async_request: Indicates if the request should be executed
                asynchronously.

        Returns:
            `threading.Thread` object handle if the `async_request` argument
            True, `None` otherwise.
        """
        return self._send_worker_command(
            WorkerManager.Command.START, async_request
        )

    def status(self) -> schemas.Worker:
        """Gets current worker status.

        Returns:
            `Worker` object.
        """
        response = self._client.get("worker/status")
        return schemas.decode(schemas.WorkerSchema, response.text)

    def stop(self, async_request: bool = False) -> Optional[threading.Thread]:
        """Stops worker.

        This method makes synchronous request to the Floq API service, thus it
        will block code execution until the TPU worker is up and running. To
        make it asynchronous, pass async_request=True.

        Args:
            async_request: Indicates if the request should be executed
                asynchronously.

        Returns:
            `threading.Thread` object handle if the `async_request` argument
            True, `None` otherwise.
        """
        return self._send_worker_command(
            WorkerManager.Command.STOP, async_request
        )

    def _send_worker_command(
        self, command: Command, async_request: bool
    ) -> Optional[threading.Thread]:
        """Sends command to the worker.

        Args:
            command: Worker command.
            async_request: Indicates if the request should be executed
                asynchronously.

        Returns:
            `threading.Thread` object handle if the `async_request` argument
             True, `None` otherwise.
        """

        def run() -> None:
            response = self._client.post(f"worker/{command.name.lower()}")

            task: schemas.TaskSubmitted = schemas.decode(
                schemas.TaskSubmittedSchema, response.text
            )
            url = f"tasks/{str(task.id)}/stream"

            self._handler.context = command
            self._handler.open_stream(url, self.on_worker_command_event)

        thread = None
        if async_request:
            thread = threading.Thread(target=run)
            thread.start()
            return thread

        run()
        return thread
