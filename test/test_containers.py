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
"""Unit test for floq.client.containers module."""
import unittest

from floq.client import (
    api_client,
    containers,
    jobs_queue,
    schemas,
    simulators,
    sse,
    worker,
)


class TestClient(unittest.TestCase):
    """Tests Client container."""

    @classmethod
    def setUpClass(cls) -> None:
        """See base class documentation."""
        cls.container = containers.Client()
        cls.container.core.config.from_dict(
            {
                "api_key": "api_key",
                "hostname": "hostname",
                "use_ssl": False,
            }
        )

    @classmethod
    def tearDownClass(cls) -> None:
        """See base class documentation."""
        cls.container.shutdown_resources()

    def test_core_container(self) -> None:
        """Tests core container."""
        obj = self.container.core.ApiClient()
        # Regular isinstance(obj, api_client.ApiClient) check is failing when
        # running all client tests, but passes when running only this test case.
        # This is a workaround to ensure obj is type of ApiClient.
        self.assertTrue(type(obj.__class__), type(api_client.ApiClient))

        obj = self.container.core.TaskStatusStreamHandler()
        self.assertTrue(isinstance(obj, sse.TaskStatusStreamHandler))

    def test_managers_container(self) -> None:
        """Tests managers container."""
        obj = self.container.managers.JobsQueueManager()
        self.assertTrue(isinstance(obj, jobs_queue.JobsQueueManager))

        obj = self.container.managers.WorkerManager()
        self.assertTrue(isinstance(obj, worker.WorkerManager))

    def test_simulators_container(self) -> None:
        """Tests simulators container."""
        obj = self.container.simulators.remote_simulators()
        for job_type, sim_class in (
            (
                schemas.JobType.EXPECTATION,
                simulators.ExpectationValuesSimulator,
            ),
            (schemas.JobType.SAMPLE, simulators.SamplesSimulator),
        ):
            self.assertTrue(isinstance(obj[job_type], sim_class))

        obj = self.container.simulators.CirqSimulator()
        self.assertTrue(isinstance(obj, simulators.CirqSimulator))
