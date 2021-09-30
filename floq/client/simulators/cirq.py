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

# pylint: disable=too-many-arguments

"""This module provides cirq based implementation of the Floq service
simulators."""

from typing import Any, Dict, List, Iterator, Optional, Union, cast
import cirq
import numpy as np

from .. import schemas
from . import floq


class CirqSimulator(
    cirq.sim.SimulatesSamples, cirq.sim.SimulatesExpectationValues
):
    """A cirq based remote simulator.

    Simulates quantum circuits on the cloud and provides interfaces of following
    Cirq simulators:

    .. _cirq.sim.simulator.SimulatesSamples:
       https://quantumai.google/reference/python/cirq/sim/SimulatesSamples
    .. _cirq.sim.simulator.SimulatesExpectationValues:
       https://quantumai.google/reference/python/cirq/sim/SimulatesExpectationValues

    - `cirq.sim.simulator.SimulatesSamples`_
    - `cirq.sim.simulator.SimulatesExpectationValues`_

    Note: The simulator does not support `cirq.sim.simulator.SimulatesSamples`
    asynchronous methods - they behave same way as the synchronous methods.
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

    ############################################################################
    # cirq.sim.simulator.SimulatesSamples                                      #
    ############################################################################

    def run(
        self,
        program: cirq.Circuit,
        param_resolver: cirq.ParamResolverOrSimilarType = None,
        repetitions: int = 1,
    ) -> cirq.Result:
        """Samples from the given Circuit.

        Args:
            program: The circuit to sample from.
            param_resolver: Parameters to run with the program.
            repetitions: The number of times to sample.

        Returns:
            Result for a run.
        """
        self._verify_sampler_input(program)

        if param_resolver is None:
            param_resolver = cirq.ParamResolver({})

        return self._simulators[schemas.JobType.SAMPLE].run(
            program, param_resolver, repetitions
        )

    def run_batch(
        self,
        programs: List[cirq.Circuit],
        params_list: Optional[List[cirq.Sweepable]] = None,
        repetitions: Union[int, List[int]] = 1,
    ) -> List[List[cirq.Result]]:
        """Runs the supplied circuits.

        Each circuit provided in `programs` will pair with the optional
        associated parameter sweep provided in the `params_list`, and be run
        with the associated repetitions provided in `repetitions` (if
        `repetitions` is an integer, then all runs will have that number of
        repetitions). If `params_list` is specified, then the number of
        circuits is required to match the number of sweeps. Similarly, when
        `repetitions` is a list, the number of circuits is required to match
        the length of this list.

        Args:
            programs: The circuits to execute as a batch.
            params_list: Parameter sweeps to use with the circuits. The number
                of sweeps should match the number of circuits and will be
                paired in order with the circuits.
            repetitions: Number of circuit repetitions to run. Can be specified
                as a single value to use for all runs, or as a list of values,
                one for each circuit.

        Returns:
            A list of lists of TrialResults. The outer list corresponds to
            the circuits, while each inner list contains the TrialResults
            for the corresponding circuit, in the order imposed by the
            associated parameter sweep.
        """
        if params_list is None:
            params_list = [None] * len(programs)
        if len(programs) != len(params_list):
            raise ValueError(
                "len(programs) and len(params_list) must match. "
                f"Got {len(programs)} and {len(params_list)}."
            )
        if isinstance(repetitions, int):
            repetitions = [repetitions] * len(programs)
        if len(programs) != len(repetitions):
            raise ValueError(
                "len(programs) and len(repetitions) must match. "
                f"Got {len(programs)} and {len(repetitions)}."
            )
        return cast(
            floq.SamplesSimulator, self._simulators[schemas.JobType.SAMPLE]
        ).run_batch(programs, params_list, repetitions)

    def run_sweep_iter(
        self,
        program: cirq.Circuit,
        params: cirq.Sweepable,
        repetitions: int = 1,
    ) -> Iterator[cirq.Result]:
        """Runs the supplied Circuit, mimicking quantum hardware.

        In contrast to run, this allows for sweeping over different parameter
        values.

        Args:
            program: The circuit to simulate.
            params: Parameters to run with the program.
            repetitions: The number of repetitions to simulate.

        Returns:
            Result list for this run; one for each possible parameter
            resolver.
        """
        self._verify_sampler_input(program)

        results = cast(
            floq.SamplesSimulator, self._simulators[schemas.JobType.SAMPLE]
        ).run_sweep(program, params, repetitions)
        for result in results:
            yield result

    def _run(
        self,
        circuit: cirq.Circuit,
        param_resolver: cirq.ParamResolver,
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
        result: cirq.Result = self._simulators[schemas.JobType.SAMPLE].run(
            circuit, param_resolver, repetitions
        )
        return result._measurements  # pylint: disable=protected-access

    @staticmethod
    def _verify_sampler_input(program: cirq.Circuit) -> None:
        """Checks if input circuit has measurements and unique measurements
        keys.

        Args:
            program: Circuit to be verified.

        Raises:
            ValueError: if the input circuit does not have measurements or
                unique keys.
        """
        if not program.has_measurements():
            raise ValueError("Circuit has no measurements to sample.")

        cirq.sim.simulator._verify_unique_measurement_keys(  # pylint: disable=protected-access
            program
        )

    ############################################################################
    # cirq.sim.simulator.SimulatesExpectationValues                            #
    ############################################################################

    def simulate_expectation_values(
        self,
        program: cirq.Circuit,
        observables: Union[cirq.PauliSumLike, List[cirq.PauliSumLike]],
        param_resolver: cirq.study.ParamResolverOrSimilarType = None,
        qubit_order: cirq.ops.QubitOrderOrList = cirq.ops.QubitOrder.DEFAULT,
        initial_state: Any = None,
        permit_terminal_measurements: bool = True,
    ) -> List[float]:
        """Simulates the supplied circuit and calculates exact expectation
        values for the given observables on its final state.

        This method has no perfect analogy in hardware. Instead compare with
        `Sampler.sample_expectation_values`, which calculates estimated
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
            ValueError: if `program` has terminal measurement(s) and
                `permit_terminal_measurements` is False.
        """
        if not isinstance(observables, list):
            observables = [observables]

        self._verify_expectation_values_input(
            [program],
            [observables],
            qubit_order,
            initial_state,
            permit_terminal_measurements,
        )

        if param_resolver is None:
            param_resolver = cirq.ParamResolver({})

        return self._simulators[schemas.JobType.EXPECTATION].run(
            program, param_resolver, observables
        )

    def simulate_expectation_values_batch(
        self,
        programs: List[cirq.circuits.Circuit],
        observables_list: List[List[cirq.PauliSumLike]],
        params_list: List[cirq.study.Sweepable],
        qubit_order: cirq.ops.QubitOrderOrList = cirq.ops.QubitOrder.DEFAULT,
        initial_state: Any = None,
        permit_terminal_measurements: bool = True,
    ) -> List[List[List[float]]]:
        """Simulates the supplied batch of circuits and calculates exact
        expectation values for the given observables of each circuit on its
        final state, sweeping over the given params for each circuit.

        This method expects a list of observables and a sweepable for each
        circuit.

        This method has no perfect analogy in hardware. Instead compare with
        `Sampler.sample_expectation_values`, which calculates estimated
        expectation values by sampling multiple times.

        Args:
            programs: A list of circuits to simulate.
            observables_list: A list of observables for each circuit.
            params_list: A Sweepable for each circuit.
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
            A list of lists of expectation-value lists. The outer index
            corresponds to the circuit, the middle index determines the sweep,
            and the inner index determines the observable. For instance,
            `results[0][1][3]` would select the fourth observable measured in
            the second sweep of the first circuit.
        """
        self._verify_expectation_values_input(
            programs,
            observables_list,
            qubit_order,
            initial_state,
            permit_terminal_measurements,
        )

        return cast(
            floq.ExpectationValuesSimulator,
            self._simulators[schemas.JobType.EXPECTATION],
        ).run_batch(programs, params_list, observables_list)

    def simulate_expectation_values_sweep(
        self,
        program: cirq.Circuit,
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
        `Sampler.sample_expectation_values`, which calculates estimated
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
            A list of expectation-value. The outer index determines the sweep,
            and the inner index determines the observable. For instance,
            `results[1][3]` would select the fourth observable measured in theR
            second sweep.
        """
        if not isinstance(observables, list):
            observables = [observables]

        self._verify_expectation_values_input(
            [program],
            [observables],
            qubit_order,
            initial_state,
            permit_terminal_measurements,
        )

        return cast(
            floq.ExpectationValuesSimulator,
            self._simulators[schemas.JobType.EXPECTATION],
        ).run_sweep(program, params, observables)

    @staticmethod
    def _verify_expectation_values_input(
        programs: List[cirq.Circuit],
        observables: List[List[cirq.PauliSumLike]],
        qubit_order: cirq.ops.QubitOrderOrList,
        initial_state: Any,
        permit_terminal_measurements: bool,
    ) -> None:
        """Verifies inputs of expectation values simulation.

        Args:
            programs: A list of circuits to simulate.
            observables: A list of observables for each circuit.
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

        Raises:
            ValueError: if any of following conditions is met:
                * each circuit has else than 21 qubits
                * qubit_order is not QubitOrder.DEFAULT
                * initial_state is not None
                * permit_terminal_measurements is not True
                * all observables are not cirq.PauliSum type
        """
        if not all(len(program.all_qubits()) >= 21 for program in programs):
            raise ValueError(
                "Expectations are currently only supported on num_qubits >= 21"
            )

        if qubit_order is not cirq.ops.QubitOrder.DEFAULT:
            raise ValueError("Only DEFAULT qubit_order is currently supported.")

        if initial_state is not None:
            raise ValueError("Only an inititial_state of None is supported.")

        if permit_terminal_measurements is not True:
            raise ValueError(
                "Terminal measurements are always allowed and will always be "
                "removed automatically"
            )

        for observable in observables:
            if not all(isinstance(op, cirq.PauliSum) for op in observable):
                raise TypeError(
                    "Observables must be of type cirq.PauliSum, got "
                    f"{[type(op) for op in observables]}."
                )
