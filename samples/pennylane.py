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
"""Integration of Floq cirq client with PennyLane-Cirq"""
import numpy as np
import pennylane as qml
import floq.client

API_KEY = "API_KEY"


def main() -> None:
    """Script entry point."""
    np.random.seed(0)

    wires = 26
    weights = np.random.randn(1, wires, 3)
    client = floq.client.CirqClient(API_KEY)

    dev = qml.device(
        "cirq.simulator",
        wires=wires,
        simulator=client.simulator,
        analytic=False,
    )

    @qml.qnode(dev)
    def my_circuit(weights):
        qml.templates.layers.StronglyEntanglingLayers(
            weights, wires=range(wires)
        )
        return qml.expval(qml.PauliZ(0))

    print(my_circuit(weights))


if __name__ == "__main__":
    main()
