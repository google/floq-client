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
import abc
from typing import Any, List
import uuid
import unittest
import unittest.mock
import cirq
import requests

from floq.client import api_client, containers, errors, schemas, simulators


class TestRemoteSimulator(unittest.TestCase):
    """Base class for testing AbstractRemoteSimulator simulators."""

    JOB_ID = uuid.uuid4()

    class AbstractCircuitProvider:
        """A helper class providing quantum circuits for unit tests."""

        @property
        @abc.abstractmethod
        def circuit(self) -> cirq.Circuit:
            """Circuit to be simulated."""
            raise NotImplementedError

        @property
        def param_resolver(self) -> cirq.ParamResolver:
            """Parameters to be used together with the circuit."""
            return cirq.ParamResolver()

    @classmethod
    def setUpClass(cls) -> None:
        """See base class documentation."""
        cls.mocked_ctx_manager = unittest.mock.Mock()
        cls.mocked_ctx_manager.__enter__ = unittest.mock.Mock()
        cls.mocked_ctx_manager.__exit__ = unittest.mock.Mock()

        cls.mocked_client = unittest.mock.Mock(api_client.ApiClient)
        cls.mocked_client.get.return_value = cls.mocked_ctx_manager

        cls.mocked_progress = unittest.mock.Mock(
            simulators.floq.SimulationProgressThread
        )
        cls.mocked_progress.return_value = cls.mocked_progress

        cls.patcher = unittest.mock.patch(
            "floq.client.simulators.floq.SimulationProgressThread",
            cls.mocked_progress,
        )
        cls.patcher.start()

        cls.container: containers.Client = containers.Client()
        cls.container.core.ApiClient.override(cls.mocked_client)

    @classmethod
    def tearDownClass(cls) -> None:
        """See base class documentation."""
        cls.container.shutdown_resources()

    @property
    @abc.abstractmethod
    def event_schema(self) -> schemas.JobStatusEvent:
        """Dataclass to be used for creating and serializing job status
        event."""

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

    def _generate_expected_job_results(
        self, clazz: schemas.JobResult, result: Any
    ) -> List[schemas.JobResult]:
        """Generates list of JobResult types objects.

        Creates a list of JobResult objects that reflects service behavior:
        - job added to the queue (NOT_STARTED)
        - job is being processed (IN_PROGRESS)
        - job is done (COMPLETE)

        Args:
            clazz: Class to be used for encoding job results.
            results: Simulation job result.

        Returns:
            List of JobResult objects.
        """
        return [
            clazz(id=self.JOB_ID, status=schemas.JobStatus.NOT_STARTED),
            clazz(
                id=self.JOB_ID,
                status=schemas.JobStatus.IN_PROGRESS,
                progress=schemas.JobProgress(),
            ),
            clazz(
                id=self.JOB_ID,
                status=schemas.JobStatus.COMPLETE,
                result=result,
            ),
        ]

    def _set_mocked_client_get_response(
        self, results: List[simulators.floq.JobContext]
    ) -> None:
        """Sets mocked_client.get method response.

        Args:
            result: List of simulation job results.
        """
        events = [
            schemas.SampleJobStatusEvent(data=x, id=self.JOB_ID)
            for x in results
        ]
        serialized_events = [
            schemas.encode(
                getattr(schemas, f"{self.event_schema.__name__}Schema"), x
            )
            for x in events
        ]

        mocked_get_response = unittest.mock.Mock(requests.Response)
        mocked_get_response.iter_lines.return_value = [
            y.encode() for x in serialized_events for y in x.split("\n")
        ]
        self.mocked_ctx_manager.__enter__.return_value = mocked_get_response

    def _verify_mocked_client_get_request(self, endpoint: str) -> None:
        """Verifies calls to the mocked_api.get mock"""
        self.mocked_client.get.assert_called_once_with(
            f"jobs/{endpoint}/{str(self.JOB_ID)}/stream", stream=True
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

    def _verify_mocked_progress(self, total_units: int) -> None:
        """Verifies calls to the mocked_progress mock.

        Args:
            total_units: Expected number of work units.
        """
        self.mocked_progress.assert_called_once_with(total_units)
        self.mocked_progress.start.assert_called_once_with()
        self.mocked_progress.finalize.assert_called_once_with()
        self.mocked_progress.join.assert_called_once_with(timeout=5)


class TestSamplesSimulator(TestRemoteSimulator):
    """Tests SamplesSimulator class behavior."""

    class CircuitProvider(TestRemoteSimulator.AbstractCircuitProvider):
        """A helper class providing quantum circuit and parameters for sampling
        simulator unit tests."""

        @property
        def circuit(self) -> cirq.Circuit:
            qubits = cirq.LineQubit.range(6)
            circuit = cirq.Circuit(
                [cirq.X(qubits[1]), cirq.X(qubits[5]), cirq.X(qubits[3])]
            )
            circuit += [cirq.measure(qubits[i]) for i in range(6)]
            return circuit

        @property
        def param_resolver(self) -> cirq.ParamResolver:
            return cirq.ParamResolver()

        @property
        def repetitions(self) -> int:
            """Number of input repetitions."""
            return 1

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.provider = TestSamplesSimulator.CircuitProvider()

    @property
    def event_schema(self) -> schemas.SampleJobStatusEvent:
        return schemas.SampleJobStatusEvent

    def setUp(self) -> None:
        """See base class documentation."""
        super().setUp()

        self.simulator = self.container.simulators.remote_simulators()[
            schemas.JobType.SAMPLE
        ]

    def test_sample_basic(self) -> None:
        """Tests run method behavior."""
        # Test setup
        expected_result = cirq.Simulator().run(
            self.provider.circuit,
            self.provider.param_resolver,
            self.provider.repetitions,
        )
        expected_job_results = self._generate_expected_job_results(
            schemas.SampleJobResult, expected_result
        )
        self._set_mocked_client_get_response(expected_job_results)

        # Run test
        actual_result = self.simulator.run(
            self.provider.circuit,
            self.provider.param_resolver,
            self.provider.repetitions,
        )

        # Verification
        self.assertEqual(actual_result, expected_result)

        context = schemas.SampleJobContext(
            self.provider.circuit,
            self.provider.param_resolver,
            self.provider.repetitions,
        )
        serialized_context = schemas.encode(
            schemas.SampleJobContextSchema,
            context,
        )
        self._verify_mocked_client_post_request("sample", serialized_context)
        self._verify_mocked_client_get_request("sample")
        self._verify_mocked_progress(expected_job_results[1].progress.total)

    def test_sample_sweep(self) -> None:
        """Tests run_sweep method behavior."""
        # Test setup
        params = [self.provider.param_resolver]

        expected_result = cirq.Simulator().run_sweep(
            self.provider.circuit,
            params,
            self.provider.repetitions,
        )
        expected_job_results = self._generate_expected_job_results(
            schemas.SampleSweepJobResult, expected_result
        )
        self._set_mocked_client_get_response(expected_job_results)

        # Run test
        actual_result = self.simulator.run_sweep(
            self.provider.circuit,
            self.provider.param_resolver,
            self.provider.repetitions,
        )

        # Verification
        self.assertEqual(actual_result, expected_result)

        context = schemas.SampleSweepJobContext(
            self.provider.circuit,
            self.provider.param_resolver,
            self.provider.repetitions,
        )
        serialized_context = schemas.encode(
            schemas.SampleSweepJobContextSchema,
            context,
        )
        self._verify_mocked_client_post_request(
            "sample/sweep", serialized_context
        )
        self._verify_mocked_client_get_request("sample")
        self._verify_mocked_progress(expected_job_results[1].progress.total)

    def test_sample_batch(self) -> None:
        """Tests run_batch method behavior."""
        # Test setup
        circuits = [self.provider.circuit]
        params = [self.provider.param_resolver]

        expected_result = cirq.Simulator().run_batch(
            circuits,
            params,
            self.provider.repetitions,
        )
        expected_job_results = self._generate_expected_job_results(
            schemas.SampleBatchJobResult, expected_result
        )
        self._set_mocked_client_get_response(expected_job_results)

        # Run test
        actual_result = self.simulator.run_batch(
            circuits, params, self.provider.repetitions
        )

        # Verification
        self.assertEqual(actual_result, expected_result)

        context = schemas.SampleBatchJobContext(
            circuits, params, self.provider.repetitions
        )
        serialized_context = schemas.encode(
            schemas.SampleBatchJobContextSchema,
            context,
        )
        self._verify_mocked_client_post_request(
            "sample/batch", serialized_context
        )
        self._verify_mocked_client_get_request("sample")
        self._verify_mocked_progress(expected_job_results[1].progress.total)

    def test_simulation_error(self) -> None:
        """Tests run method behavior: job failed."""
        # Test setup
        expected_job_results = [
            schemas.SampleJobResult(
                id=self.JOB_ID, status=schemas.JobStatus.NOT_STARTED
            ),
            schemas.SampleJobResult(
                id=self.JOB_ID,
                status=schemas.JobStatus.IN_PROGRESS,
                progress=schemas.JobProgress(),
            ),
            schemas.SampleJobResult(
                id=self.JOB_ID,
                status=schemas.JobStatus.ERROR,
                error_message="Simulation failed",
            ),
        ]

        self._set_mocked_client_get_response(expected_job_results)

        def exit_side_effect(_, exc_value, __) -> None:
            raise exc_value

        self.mocked_ctx_manager.__exit__.side_effect = exit_side_effect

        # Run test
        with self.assertRaises(errors.SimulationError):
            self.simulator.run(
                self.provider.circuit,
                self.provider.param_resolver,
                self.provider.repetitions,
            )

        # Verification
        context = schemas.SampleJobContext(
            self.provider.circuit,
            self.provider.param_resolver,
            self.provider.repetitions,
        )
        serialized_context = schemas.encode(
            schemas.SampleJobContextSchema,
            context,
        )
        self._verify_mocked_client_post_request("sample", serialized_context)
        self._verify_mocked_client_get_request("sample")
        self._verify_mocked_progress(expected_job_results[1].progress.total)

    def test_serialization_error(self) -> None:
        """Tests serialization error."""
        with self.assertRaises(errors.SerializationError):
            self.simulator.run(None, 1234, "test")


class TestExpectationValuesSimulator(TestRemoteSimulator):
    """Tests ExpectationValuesSimulator class behavior."""

    class CircuitProvider(TestRemoteSimulator.AbstractCircuitProvider):
        """A helper class providing quantum circuit and parameters for
        expectation valeus simulator unit tests."""

        @property
        def circuit(self) -> cirq.Circuit:
            circuit = cirq.Circuit([cirq.X(q) for q in self.qubits])
            return circuit

        @property
        def observables(self) -> List[cirq.PauliSum]:
            """List of observables to be used together with the circuit."""
            return [cirq.X(self.qubits[0]) + cirq.Y(self.qubits[1])]

        @property
        def qubits(self) -> List[cirq.LineQubit]:
            """List of qubits."""
            return cirq.LineQubit.range(26)

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.provider = TestExpectationValuesSimulator.CircuitProvider()

    @property
    def event_schema(self) -> schemas.ExpectationJobStatusEvent:
        return schemas.ExpectationJobStatusEvent

    def setUp(self) -> None:
        """See base class documentation."""
        super().setUp()

        self.simulator = self.container.simulators.remote_simulators()[
            schemas.JobType.EXPECTATION
        ]

    def test_expectation_basic(self) -> None:
        """Verifies run method behavior."""
        # Test setup
        expected_result = [1.1]
        expected_job_results = self._generate_expected_job_results(
            schemas.ExpectationJobResult, expected_result
        )
        self._set_mocked_client_get_response(expected_job_results)

        # Run test
        actual_result = self.simulator.run(
            self.provider.circuit,
            self.provider.param_resolver,
            self.provider.observables,
        )

        # Verification
        self.assertEqual(actual_result, expected_result)

        context = schemas.ExpectationJobContext(
            self.provider.circuit,
            self.provider.param_resolver,
            self.provider.observables,
        )
        serialized_context = schemas.encode(
            schemas.ExpectationJobContextSchema,
            context,
        )
        self._verify_mocked_client_post_request("exp", serialized_context)
        self._verify_mocked_client_get_request("exp")
        self._verify_mocked_progress(expected_job_results[1].progress.total)

    def test_expectation_sweep(self) -> None:
        """Verifies run_sweep method behavior."""
        # Test setup
        params = [self.provider.param_resolver]
        expected_result = [[1.1]]

        expected_job_results = self._generate_expected_job_results(
            schemas.ExpectationSweepJobResult, expected_result
        )
        self._set_mocked_client_get_response(expected_job_results)

        # Run test
        actual_result = self.simulator.run_sweep(
            self.provider.circuit,
            params,
            self.provider.observables,
        )

        # Verification
        self.assertEqual(actual_result, expected_result)

        context = schemas.ExpectationSweepJobContext(
            self.provider.circuit,
            params,
            self.provider.observables,
        )
        serialized_context = schemas.encode(
            schemas.ExpectationSweepJobContextSchema,
            context,
        )
        self._verify_mocked_client_post_request("exp/sweep", serialized_context)
        self._verify_mocked_client_get_request("exp")
        self._verify_mocked_progress(expected_job_results[1].progress.total)

    def test_expectation_batch(self) -> None:
        """Verifies run_batch method behavior."""
        # Test setup
        circuits = [self.provider.circuit]
        params = [self.provider.param_resolver]
        observables = [self.provider.observables]
        expected_result = [[[1.1]]]

        expected_job_results = self._generate_expected_job_results(
            schemas.ExpectationBatchJobResult, expected_result
        )
        self._set_mocked_client_get_response(expected_job_results)

        # Run test
        actual_result = self.simulator.run_batch(circuits, params, observables)

        # Verification
        self.assertEqual(actual_result, expected_result)

        context = schemas.ExpectationBatchJobContext(
            circuits, params, observables
        )
        serialized_context = schemas.encode(
            schemas.ExpectationBatchJobContextSchema,
            context,
        )
        self._verify_mocked_client_post_request("exp/batch", serialized_context)
        self._verify_mocked_client_get_request("exp")
        self._verify_mocked_progress(expected_job_results[1].progress.total)

    def test_serialization_error(self) -> None:
        """Tests serialization error."""
        with self.assertRaises(errors.SerializationError):
            self.simulator.run("test", None, 1234)
