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
"""Unit test for the floq module."""
import importlib
import time
from typing import List
import uuid
import unittest
import unittest.mock
import cirq
import requests

from floq.client import api_client, containers, errors, schemas, simulators


class TestRemoteSimulator(unittest.TestCase):
    """Base class for testing AbstractRemoteSimulator simulators."""

    JOB_ID = uuid.uuid4()

    @classmethod
    def setUpClass(cls) -> None:
        """See base class documentation."""
        cls.patchers: List[unittest.mock._patch] = []

        cls.mocked_time = unittest.mock.Mock(time.time)
        patcher = unittest.mock.patch("time.time", cls.mocked_time)
        cls.patchers.append(patcher)

        cls.mocked_sleep = unittest.mock.Mock(time.sleep)
        patcher = unittest.mock.patch("time.sleep", cls.mocked_sleep)
        cls.patchers.append(patcher)

        for patch in cls.patchers:
            patch.start()

        importlib.reload(containers)

        cls.mocked_client = unittest.mock.Mock(api_client.ApiClient)

        cls.container: containers.Client = containers.Client()
        cls.container.core.ApiClient.override(cls.mocked_client)

    @classmethod
    def tearDownClass(cls) -> None:
        """See base class documentation."""
        for patcher in cls.patchers:
            patcher.stop()

        cls.container.shutdown_resources()

    def setUp(self) -> None:
        """See base class documentation."""
        job_submitted = schemas.JobSubmitted(self.JOB_ID)
        mocked_post_response = unittest.mock.Mock(requests.Response)
        mocked_post_response.text = schemas.encode(
            schemas.JobSubmittedSchema, job_submitted
        )
        self.mocked_client.post.return_value = mocked_post_response

    def tearDown(self) -> None:
        """See base class documentation."""
        for attr in dir(self):
            if attr.startswith("mocked_"):
                getattr(self, attr).reset_mock()

    def _verify_mocked_client_get_request(self, endpoint: str) -> None:
        """Verifies calls to the mocked_api.get mock"""
        self.mocked_client.get.assert_called_once_with(
            f"jobs/{endpoint}/{str(self.JOB_ID)}/results"
        )

    def _verify_mocked_client_post_request(
        self,
        endpoint: str,
        context: str,
    ) -> None:
        """Verifies calls to the mocked_api.post mock"""
        self.mocked_client.post.assert_called_once_with(
            f"jobs/{endpoint}/submit", context
        )


class TestSamplesSimulator(TestRemoteSimulator):
    """Tests SamplesSimulator class behavior."""

    def setUp(self) -> None:
        """See base class documentation."""
        super().setUp()
        self.simulator = self.container.simulators.remote_simulators()[
            schemas.JobType.SAMPLE
        ]

    def tearDown(self) -> None:
        """See base class documentation."""
        super().tearDown()
        self.mocked_time.side_effect = None

    def test_sample_basic(self) -> None:
        """Tests run method behavior."""
        # Test setup
        qubits = cirq.LineQubit.range(6)
        circuit = cirq.Circuit(
            [cirq.X(qubits[1]), cirq.X(qubits[5]), cirq.X(qubits[3])]
        )
        circuit += [cirq.measure(qubits[i]) for i in range(6)]
        expected_result = cirq.Simulator().run(circuit)

        job_result = schemas.SampleJobResult(
            id=self.JOB_ID,
            status=schemas.JobStatus.COMPLETE,
            result=expected_result,
        )
        mocked_get_response = unittest.mock.Mock(requests.Response)
        mocked_get_response.text = schemas.encode(
            schemas.SampleJobResultSchema, job_result
        )
        self.mocked_client.get.return_value = mocked_get_response

        self.mocked_time.return_value = 1

        # Run test
        actual_result = self.simulator.run(circuit, cirq.ParamResolver(None), 1)

        # Verification
        self.assertEqual(actual_result, expected_result._measurements)

        context = schemas.SampleJobContext(circuit, cirq.ParamResolver(None), 1)
        serialized_context = schemas.encode(
            schemas.SampleJobContextSchema,
            context,
        )
        self._verify_mocked_client_post_request("sample", serialized_context)
        self._verify_mocked_client_get_request("sample")

        self.assertEqual(self.mocked_time.call_count, 2)
        self.mocked_sleep.assert_not_called()

    def test_simulation_error(self) -> None:
        """Tests run method behavior: job failed."""
        # Test setup
        qubits = cirq.LineQubit.range(1)
        circuit = cirq.Circuit([cirq.X(qubits[0]), cirq.measure(qubits[0])])

        job_result = schemas.SampleJobResult(
            error_message="Simulation failed",
            id=self.JOB_ID,
            status=schemas.JobStatus.ERROR,
        )
        mocked_get_response = unittest.mock.Mock(requests.Response)
        mocked_get_response.text = schemas.encode(
            schemas.SampleJobResultSchema, job_result
        )
        self.mocked_client.get.return_value = mocked_get_response

        self.mocked_time.return_value = 1

        # Run test
        with self.assertRaises(errors.SimulationError):
            self.simulator.run(circuit, cirq.ParamResolver(None), 1)

        # Verification
        context = schemas.SampleJobContext(
            circuit,
            cirq.ParamResolver(None),
        )
        serialized_context = schemas.encode(
            schemas.SampleJobContextSchema,
            context,
        )
        self._verify_mocked_client_post_request("sample", serialized_context)
        self._verify_mocked_client_get_request("sample")

        self.assertEqual(self.mocked_time.call_count, 2)
        self.mocked_sleep.assert_not_called()

    def test_polling_timeout_error(self) -> None:
        """Tests run method behavior: polling timed out."""
        # Test setup
        qubits = cirq.LineQubit.range(1)
        circuit = cirq.Circuit([cirq.X(qubits[0]), cirq.measure(qubits[0])])

        job_result = schemas.SampleJobResult(
            id=self.JOB_ID, status=schemas.JobStatus.IN_PROGRESS
        )
        mocked_get_response = unittest.mock.Mock(requests.Response)
        mocked_get_response.text = schemas.encode(
            schemas.SampleJobResultSchema, job_result
        )
        self.mocked_client.get.return_value = mocked_get_response

        max_size = (
            len(simulators.floq.AbstractRemoteSimulator._BACKOFF_SECONDS) + 1
        )
        side_effects = [0] + list(range(1, max_size)) + [300]
        self.mocked_time.side_effect = side_effects

        # Run test
        with self.assertRaises(errors.PollingTimeoutError):
            self.simulator.run(circuit, cirq.ParamResolver(None), 1)

        # Verification
        context = schemas.SampleJobContext(
            circuit,
            cirq.ParamResolver(None),
        )
        serialized_context = schemas.encode(
            schemas.SampleJobContextSchema,
            context,
        )
        self._verify_mocked_client_post_request("sample", serialized_context)
        call_args_list = [
            ((f"jobs/sample/{str(self.JOB_ID)}/results",),)
            for _ in range(
                len(simulators.floq.AbstractRemoteSimulator._BACKOFF_SECONDS)
            )
        ]
        self.assertEqual(self.mocked_client.get.call_args_list, call_args_list)

        self.assertEqual(self.mocked_time.call_count, len(side_effects))

        call_args_list = [
            ((x,),)
            for x in simulators.floq.AbstractRemoteSimulator._BACKOFF_SECONDS
        ]
        self.assertEqual(self.mocked_sleep.call_args_list, call_args_list)

    def test_resume_polling_error(self) -> None:
        """Tests resume_polling method behavior: no previous job id."""
        # Run test
        with self.assertRaises(errors.ResumePollingError):
            self.simulator.resume_polling()

    def test_serialization_error(self) -> None:
        """Tests serialization error."""
        with self.assertRaises(errors.SerializationError):
            self.simulator.run(None, 1234, "test")


class TestExpectationValuesSimulator(TestRemoteSimulator):
    """Tests ExpectationValuesSimulator class behavior."""

    def setUp(self) -> None:
        """See base class documentation."""
        super().setUp()
        self.simulator = self.container.simulators.remote_simulators()[
            schemas.JobType.EXPECTATION
        ]

    def test_expectation_basic(self) -> None:
        """Verifies simulate_expectation_values method behavior."""
        # Test setup
        qubits = cirq.LineQubit.range(26)
        circuit = cirq.Circuit([cirq.X(q) for q in qubits])
        observables = [cirq.X(qubits[0]) + cirq.Y(qubits[1])]

        expected_result = [1.1]

        job_result = schemas.ExpectationJobResult(
            id=self.JOB_ID,
            status=schemas.JobStatus.COMPLETE,
            result=expected_result,
        )
        mocked_get_response = unittest.mock.Mock(requests.Response)
        mocked_get_response.text = schemas.encode(
            schemas.ExpectationJobResultSchema, job_result
        )
        self.mocked_client.get.return_value = mocked_get_response

        self.mocked_time.return_value = 1

        # Run test
        actual_result = self.simulator.run(
            circuit,
            cirq.ParamResolver(None),
            observables,
        )

        # Verification
        self.assertEqual(actual_result, expected_result)

        context = schemas.ExpectationJobContext(
            circuit,
            cirq.ParamResolver(None),
            observables,
        )
        serialized_context = schemas.encode(
            schemas.ExpectationJobContextSchema,
            context,
        )
        self._verify_mocked_client_post_request("exp", serialized_context)
        self._verify_mocked_client_get_request("exp")

        self.assertEqual(self.mocked_time.call_count, 2)
        self.mocked_sleep.assert_not_called()

    def test_serialization_error(self) -> None:
        """Tests serialization error."""
        with self.assertRaises(errors.SerializationError):
            self.simulator.run("test", None, 1234)
