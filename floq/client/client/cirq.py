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
"""Floq service cirq client."""
from ..simulators import cirq
from . import abstract


class CirqClient(abstract.AbstractClient):  # pylint: disable=too-few-public-methods
    """Creates and initializes Floq client resources.

    This class provides CirqSimulator class instance, a cirq based simulator
    that simulates quantum circuits on the cloud.
    """

    @property
    def simulator(self) -> cirq.CirqSimulator:
        """CirqSimulator class instance.

        This is the client for the floq service and implements the following
        cirq simulation interfaces:
            - cirq.sim.simulator.SimulatesSamples
            - cirq.sim.simulator.SimulatesExpectationValues
        """
        return self._container.simulators.CirqSimulator()
