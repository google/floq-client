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
"""This module provides interface for managing pending jobs queue."""

import json
from typing import Any, Optional
import uuid

from . import api_client, schemas, sse


class JobsQueueManager:
    """Manages jobs queue.

    The Floq service does not handle the flush queue request immediately, but
    schedules it for execution and starts emitting events along with run
    progress. Thus, when calling the flush method the manager sends the
    request to the service and opens an event stream connection. Every time
    a new message is received, the :meth:`on_jobs_queue_flushed` callback method
    is called and prints an output message once the execution is done.
    """

    def __init__(
        self,
        client: api_client.ApiClient,
        handler: sse.EventStreamHandler,
    ) -> None:
        """Creates JobsQueueManager class instance.

        Args:
            client: Reference to ApiClient object.
            handler: Reference to EventStreamHandler type object.
        """
        self._client = client
        self._handler = handler

    def flush(self) -> None:
        """Clears jobs queue.

        This is asynchronous task, the server will emit execution progress via
        events stream.
        """
        response = self._client.delete("jobs/queue")

        task: schemas.TaskSubmitted = schemas.decode(
            schemas.TaskSubmittedSchema, response.text
        )
        url = f"tasks/{str(task.id)}/stream"

        self._handler.open_stream(url, self.on_jobs_queue_flushed)

    def get(self) -> schemas.JobsQueue:
        """Gets jobs queue.

        Returns:
            `JobsQueue` object.
        """
        response = self._client.get("jobs/queue")
        return schemas.decode(schemas.JobsQueueSchema, response.text)

    def get_pending_job(self, job_id: uuid.UUID) -> schemas.PendingJob:
        """Gets pending job details.

        Args:
            job_id: Unique job id.

        Returns:
            `PendingJob` object.
        """
        response = self._client.get(f"jobs/queue/{str(job_id)}")
        return schemas.decode(schemas.PendingJobSchema, response.text)

    def on_jobs_queue_flushed(  # pylint: disable=no-self-use
        self, event: schemas.TaskStatusEvent, _context: Optional[Any]
    ) -> None:
        """Callback function triggered after receiving a flush jobs queue
        progress event.

        Args:
            event: Received event.
            context: Optional user context data passed together with the
                event.
        """
        if event.data.state != schemas.TaskState.DONE:
            return

        if event.data.success:
            print("Jobs queue flushed")
        else:
            print("Failed to flush jobs queue: {event.data.error}")

    def print_pending_jobs(self) -> None:
        """Prints pending jobs."""
        buffer = []
        queue = self.get()
        for idx, job_id in enumerate(queue.ids):
            job = self.get_pending_job(job_id)
            buffer.append(
                {
                    "id": str(job.id),
                    "idx": idx,
                    "status": job.status.name,
                    "type": job.type.name,
                }
            )

        print(json.dumps(buffer, indent=4, sort_keys=True))
