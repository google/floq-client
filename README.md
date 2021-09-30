# Floq API client

This client uses the cirq interface to submit quantum circuits to the Floq
Service. This client is designed to be simple to use for those familiar
with the `cirq.Simulator` interface.

## Installation

```bash
python3 -m virtualenv venv --python=python3.8  # At least Python 3.7
source venv/bin/activate
pip install floq_client
```

## Documentation

Full documentation is available at https://floq-client.readthedocs.io/

## Usage

Currently the Floq client supports cirq's `SimulatesSamples` and the
`SimulatesExpectationValues` simulators. These interfaces include methods for
running sampling and calculating expectation values of single circuits, batches
of circuits or circuits to be resolved with parameter value sweeps.

Check out the samples in the [samples](./samples) directory.

### SimulatesSamples

```python
import floq.client

qubits = cirq.LineQubit.range(26)
param_resolver = cirq.ParamResolver({'a': 1})
a = sympy.Symbol('a')
circuit = cirq.Circuit(
    [cirq.X(q) ** a for q in qubits] +
    [cirq.measure(q) for q in qubits])

client = floq.client.CirqClient("my_api_key")
result = client.simulator.run(circuit, param_resolver) # Results from the cloud hurray!
```

See
[SimulatesSamples](https://quantumai.google/reference/python/cirq/sim/SimulatesSamples)
interface documentation for more information.

> Note: This client does not support the `async` run calls currently.

### SimulatesExpectationValues

See
[SimulatesExpectationValues](https://quantumai.google/reference/python/cirq/sim/SimulatesExpectationValues)
interface documentation for more information.

The client also provides calculation of expectation values against
`cirq.PauliSum` observables:

```python
import floq.client

client = floq.client.CirqClient("my_api_key")

# Find expectation against a single Paulisum
magnetization_op = sum([cirq.Z(q) for q in qubits])
client.simulator.simulate_expectation_values(
    circuit,
    magnetization_op,
    param_resolvers)

    # returns [exp_value]

# Or against multiple
client.simulator.simulate_expectation_values(
    circuit,
    [magnetization_op, cirq.X(qubits[0]) + cirq.Y(qubits[0])]
)
    # returns [exp1, exp2] - one expectation per observable

# Also run sweeps over param_resolver values
client.simulator.simulate_expectation_values_sweep(
    circuit,
    [observable1, observable2],
    cirq.Sweepable
)
    # returns [[exp1, exp2], ...] - one list of expectations per param set
```

> Note: The SimulatesExpectationValues interface is available in cirq>=0.10.0.

### Jobs Queue manager

Floq client also provides an interface for inspecting and flushing pending jobs
queue. Each time a quantum circuit is submitted to the cloud, the Floq service
replies with unique job id and the job is queued for the execution.

The example code is located in [jobs_queue.py](./samples/jobs_queue.py) sample
file.

### TPU worker manager

Each individual API key is bound to dedicated TPU worker running in the cloud.
The Floq Client provides an interace for starting, stopping or restarting the
worker (in case it enters into some unexpected state). Additionally, you can
always check current worker status.

The example code is located in [worker_manager.py](./samples/worker_manager.py)
sample file.

## CLI script

Both jobs queue and TPU worker can be controlled manually using provided
[CLI script](./scripts/cli.py). Simply provide Floq API key as the input
argument and the resource command as shown below:

```shell
# Jobs queue commands
floq-client API_KEY jobs {display,flush}

# TPU worker commands
floq-client API_KEY worker {restart,start,stop,status}
```

## PennyLane-Cirq with Floq

To use Floq-backend in PennyLane, please install the latest version of
[PennyLane-Cirq](https://github.com/PennyLaneAI/pennylane-cirq) plugin.
The sample code is located in the [pennylane.py](./samples/pennylane.py) file.

## Caveats

Keep in mind that you are on the frontier and this is a very experimental
service! There will be trials, tribulations, and bugs!

Please let us know about issues you encounter and mail us at
[floq-devs@google.com](mailto:floq-devs@google.com).

That being said there are a few known limitations at this point. In order to be
conservative we have implemented restrictions on the size of circuits, number
of observables, etc... We are working hard to push this forward, bear with us.

Enjoy!
