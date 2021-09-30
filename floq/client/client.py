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
"""This module provides interfaces for Floq service clients."""
import abc
from typing import Any

from . import containers, jobs_queue, simulators, worker


class AbstractClient(abc.ABC):  # pylint: disable=too-few-public-methods
    """An abstract Floq service client.

    Abstract class that initializes the API client and provides the remote
    simulator. The subclass must implement :meth:`simulator` property method and
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
                "hostname": "floq.endpoints.sandbox-at-alphabet-floq-prod.cloud.goog",
                "use_ssl": True,
            }
        )

    @property
    def jobs_queue(self) -> jobs_queue.JobsQueueManager:
        """:obj:`floq.client.jobs_queue.JobsQueueManager`: Floq service jobs
        queue manager."""
        return self._container.managers.JobsQueueManager()

    @property
    @abc.abstractmethod
    def simulator(self) -> Any:
        """:obj:`Any`: Remote simulator."""

    @property
    def tpu_worker(self) -> worker.WorkerManager:
        """:obj:`floq.client.worker.WorkerManager`: Floq service TPU worker
        manager."""
        return self._container.managers.WorkerManager()


class CirqClient(AbstractClient):  # pylint: disable=too-few-public-methods
    """Floq service client for cirq based remote simulator.

    This class provides :obj:`floq.client.simulators.cirq.CirqSimulator` as the
    default simulator, a cirq based implementation that simulates quantum
    circuits on the cloud.
    """

    @property
    def simulator(self) -> simulators.CirqSimulator:
        """:obj:`floq.client.simulators.cirq.CirqSimulator`: cirq based remote
        simulator.
        """
        return self._container.simulators.CirqSimulator()
