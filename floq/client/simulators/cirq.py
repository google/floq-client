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
"""Cirq based implementation of the Floq service simulators."""
from typing import Any, Dict, List, Union
import cirq
import numpy as np

from .. import schemas
from . import floq


class CirqSimulator(
    cirq.sim.simulator.SimulatesSamples,
    cirq.sim.simulator.SimulatesExpectationValues,
):
    """Floq service client based on the cirq simulator.

    Simulates quantum circuits on the cloud and provides interfaces of following
    Cirq simulators:
        - cirq.sim.simulator.SimulatesSamples
        - cirq.sim.simulator.SimulatesExpectationValues
    """

    def __init__(
        self,
        simulators: Dict[
            schemas.JobType,
            floq.AbstractRemoteSimulator,
        ],
    ) -> None:
        """Creates CirqSimulator class instance.

        Args:
            simulators: Dictionary mapping JobType to AbstractRemoteSimulator
            objects.
        """
        self._simulators = simulators

    def _run(
        self,
        circuit: cirq.circuits.Circuit,
        param_resolver: cirq.study.ParamResolver,
        repetitions: int,
    ) -> Dict[str, np.ndarray]:
        """Run a simulation, mimicking quantum hardware.

        Args:
            circuit: The circuit to simulate.
            param_resolver: Parameters to run with the program.
            repetitions: Number of times to repeat the run. It is expected that
                this is validated greater than zero before calling this method.

        Returns:
            A dictionary from measurement gate key to measurement
            results. Measurement results are stored in a 2-dimensional
            numpy array, the first dimension corresponding to the repetition
            and the second to the actual boolean measurement results (ordered
            by the qubits being measured.)
        """
        return self._simulators[schemas.JobType.SAMPLE].run(
            circuit, param_resolver, repetitions
        )

    def simulate_expectation_values(
        self,
        program: cirq.circuits.Circuit,
        observables: Union[cirq.PauliSumLike, List[cirq.PauliSumLike]],
        param_resolver: cirq.study.ParamResolverOrSimilarType = None,
        qubit_order: cirq.ops.QubitOrderOrList = cirq.ops.QubitOrder.DEFAULT,
        initial_state: Any = None,
        permit_terminal_measurements: bool = True,
    ) -> List[float]:
        """Simulates the supplied circuit and calculates exact expectation
        values for the given observables on its final state.

        This method has no perfect analogy in hardware. Instead compare with
        Sampler.sample_expectation_values, which calculates estimated
        expectation values by sampling multiple times.

        Args:
            program: The circuit to simulate.
            observables: An observable or list of observables.
            param_resolver: Parameters to run with the program.
            qubit_order: Determines the canonical ordering of the qubits. This
                is often used in specifying the initial state, i.e. the
                ordering of the computational basis states.
            initial_state: The initial state for the simulation. The form of
                this state depends on the simulation implementation. See
                documentation of the implementing class for details.
            permit_terminal_measurements: If the provided circuit ends with
                measurement(s), this method will generate an error unless this
                is set to True. This is meant to prevent measurements from
                ruining expectation value calculations.

        Returns:
            A list of expectation values, with the value at index `n`
            corresponding to `observables[n]` from the input.

        Raises:
            ValueError if 'program' has terminal measurement(s) and
            'permit_terminal_measurements' is False.
        """
        return super().simulate_expectation_values(
            program,
            observables,
            param_resolver,
            qubit_order,
            initial_state,
            permit_terminal_measurements,
        )

    def simulate_expectation_values_sweep(
        self,
        program: cirq.circuits.Circuit,
        observables: Union[cirq.PauliSumLike, List[cirq.PauliSumLike]],
        params: cirq.study.Sweepable,
        qubit_order: cirq.ops.QubitOrderOrList = cirq.ops.QubitOrder.DEFAULT,
        initial_state: Any = None,
        permit_terminal_measurements: bool = True,
    ) -> List[List[float]]:
        """Simulates the supplied circuit and calculates exact expectation
        values for the given observables on its final state, sweeping over the
        given params.

        This method has no perfect analogy in hardware. Instead compare with
        Sampler.sample_expectation_values, which calculates estimated
        expectation values by sampling multiple times.

        Args:
            program: The circuit to simulate.
            observables: An observable or list of observables.
            params: Parameters to run with the program.
            qubit_order: Determines the canonical ordering of the qubits. This
                is often used in specifying the initial state, i.e. the
                ordering of the computational basis states.
            initial_state: The initial state for the simulation. The form of
                this state depends on the simulation implementation. See
                documentation of the implementing class for details.
            permit_terminal_measurements: If the provided circuit ends in a
                measurement, this method will generate an error unless this
                is set to True. This is meant to prevent measurements from
                ruining expectation value calculations.

        Returns:
            A list of expectation-value lists. The outer index determines the
            sweep, and the inner index determines the observable. For instance,
            results[1][3] would select the fourth observable measured in the
            second sweep.

        Raises:
            ValueError if 'program' has terminal measurement(s) and
            'permit_terminal_measurements' is False.
        """
        if len(program.all_qubits()) < 26:
            raise ValueError(
                "Expectations are currently only supported on num_qubits >= 26"
            )
        if qubit_order is not cirq.QubitOrder.DEFAULT:
            raise ValueError(
                "A non-default qubit order is currently not supported",
            )
        if initial_state is not None:
            raise ValueError("An initial state is currently not supported")
        if permit_terminal_measurements is not True:
            raise ValueError(
                "Terminal measurements are always allowed and"
                " will always be removed automatically"
            )
        if not isinstance(observables, cirq.PauliSum):
            if not all(isinstance(op, cirq.PauliSum) for op in observables):
                raise TypeError(
                    "Observables must be Union[cirq.PauliSum,"
                    " List[cirq.PauliSum]] type"
                )

        return [
            self._simulators[schemas.JobType.EXPECTATION].run(
                program, param_resolver, observables
            )
            for param_resolver in cirq.to_resolvers(params)
        ]
