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
"""Floq service abstract client."""
import abc
from typing import Any

from .. import containers, jobs_queue, worker

class AbstractClient(abc.ABC):  # pylint: disable=too-few-public-methods
    """Creates and initializes Floq client resources.

    This is abstract class that initializes Floq API client and provides client
    simulator. The subclass must implement simulator() property method and
    return concrete simulator implementation.
    """

    def __init__(self, api_key: str) -> None:
        """Creates AbstractClient class instance.

        Args:
            api_key: Floq API key.
        """
        self._container = containers.Client()
        self._container.core.config.from_dict(
            {
                "api_key": api_key,
                "hostname": "floq.endpoints.quantum-x99.cloud.goog",
                "use_ssl": True,
            }
        )

    @property
    def jobs_queue(self) -> jobs_queue.JobsQueueManager:
        """Floq service jobs queue manager."""
        return self._container.managers.JobsQueueManager()

    @abc.abstractproperty
    def simulator(self) -> Any:
        """Floq service client simulator."""

    @property
    def tpu_worker(self) -> worker.WorkerManager:
        """Floq service TPU worker manager."""
        return self._container.managers.WorkerManager()