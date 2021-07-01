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
"""Unit test for the cirq module."""
import unittest
import unittest.mock
import cirq

from floq.client import containers, errors, schemas, simulators


# TODO(b/191300572): Add the follow run method tests
# * None, Actual, Multi - param_resolvers values and throw handling
# * run_sweep - values
# TODO(b/191301119): Add the following expectation method tests
# * None, Single, Multi Paulisums as observalbe argument
# * simulate_expectation_values_sweep input parameters
class TestCirqSimulator(unittest.TestCase):
    """Tests CirqSimulator class behavior."""

    @classmethod
    def setUpClass(cls) -> None:
        """See base class documentation."""
        cls.mocked_simulator = unittest.mock.Mock(
            simulators.floq.AbstractRemoteSimulator
        )
        cls.mocked_simulator.return_value = cls.mocked_simulator

        cls.container: containers.Client = containers.Client()
        cls.container.simulators.remote_simulators.override(
            {x: cls.mocked_simulator for x in schemas.JobType}
        )

    @classmethod
    def tearDownClass(cls) -> None:
        """See base class documentation."""
        cls.container.shutdown_resources()

    def setUp(self) -> None:
        """See base class documentation."""
        self.simulator = self.container.simulators.CirqSimulator()

    def tearDown(self) -> None:
        """See base class documentation."""
        for attr in dir(self):
            if attr.startswith("mocked_"):
                getattr(self, attr).reset_mock()

    def test_run(self) -> None:
        """Tests run method behavior."""
        qubits = cirq.LineQubit.range(6)
        circuit = cirq.Circuit(
            [cirq.X(qubits[1]), cirq.X(qubits[5]), cirq.X(qubits[3])]
        )
        circuit += [cirq.measure(qubits[i]) for i in range(6)]
        expected_result = cirq.Simulator().run(circuit)

        self.mocked_simulator.run.return_value = expected_result._measurements

        # Run test
        actual_result = self.simulator.run(circuit)

        # Verification
        self.assertEqual(actual_result, expected_result)
        self.mocked_simulator.run.assert_called_once_with(
            circuit, cirq.ParamResolver(None), 1
        )

    def test_simulate_expectation_values(self) -> None:
        """Tests simulate_expectation_values method behavior."""
        # Test setup
        expected_result = [1.1]
        self.mocked_simulator.run.return_value = expected_result

        # Run test
        qubits = cirq.LineQubit.range(26)
        circuit = cirq.Circuit([cirq.X(q) for q in qubits])
        observables = [cirq.X(qubits[0]) + cirq.Y(qubits[1])]
        actual_result = self.simulator.simulate_expectation_values(
            circuit,
            observables,
        )

        # Verification
        self.assertEqual(actual_result, expected_result)
        self.mocked_simulator.run.assert_called_once_with(
            circuit, cirq.ParamResolver(None), observables
        )

    def test_resume_polling(self) -> None:
        """Tests resume_polling method behavior."""
        # Test setup
        self.mocked_simulator.can_resume_polling = True
        self.mocked_simulator.resume_polling.return_value = None

        # Run test
        result = self.simulator.resume_polling()

        # Verification
        self.assertIsNone(result)
        self.mocked_simulator.resume_polling.assert_called_once()

    def test_resume_polling_no_previous_job(self) -> None:
        """Tests resume_polling method behavior: current job is unset"""
        # Test setup
        self.mocked_simulator.can_resume_polling = False

        # Run test
        with self.assertRaises(errors.ResumePollingError):
            self.simulator.resume_polling()

        # Verification
        self.mocked_simulator.resume_polling.assert_not_called()
