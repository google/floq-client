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
"""Example of TPU worker management.

This code makes synchronous request to Floq service to start TPU worker and
sends circuit for execution regardless of the worker status. Finally, when the
quantum circuit simulation is done, the script sends request to stop the worker.
"""
import cirq
import floq.client
import floq.client.schemas

API_KEY = "api_key"


def main() -> None:
    """Script entry point."""

    client = floq.client.CirqClient(API_KEY)

    # Start worker
    client.tpu_worker.start(True)

    # Submit circuit
    qubits = cirq.LineQubit.range(1)
    circuit = cirq.Circuit([cirq.X(qubits[0]), cirq.measure(qubits[0])])
    result = client.simulator.run(circuit)
    print(result)

    # Stop worker
    thread = client.tpu_worker.stop(True)
    thread.join()


if __name__ == "__main__":
    main()
