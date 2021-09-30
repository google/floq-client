.. module:: floq.client

.. _cirq.sim.simulator.SimulatesSamples:
    https://quantumai.google/reference/python/cirq/sim/SimulatesSamples
.. _cirq.sim.simulator.SimulatesExpectationValues:
    https://quantumai.google/reference/python/cirq/sim/SimulatesExpectationValues
.. _samples:
    https://github.com/google/floq-client/tree/main/samples

Quickstart
==========

This guide will walk you through the basics of Floq Client.

Currently the Floq client supports following cirq's simulators:

- `cirq.sim.simulator.SimulatesSamples`_
- `cirq.sim.simulator.SimulatesExpectationValues`_

These interfaces include methods for running sampling and calculating
expectation values of single circuits, batches of circuits or circuits to be
resolved with parameter value sweeps.

Simulate samples
----------------

::

    import cirq
    import floq.client

    qubits = cirq.LineQubit.range(26)
    param_resolver = cirq.ParamResolver({'a': 1})
    a = sympy.Symbol('a')
    circuit = cirq.Circuit(
        [cirq.X(q) ** a for q in qubits] +
        [cirq.measure(q) for q in qubits]
    )

    client = floq.client.CirqClient("my_api_key")
    result = client.simulator.run(circuit, param_resolver)
    print(result)

Simulate expectation values
---------------------------

::

    import cirq
    import floq.client

    qubits = cirq.LineQubit.range(26)
    magnetization_op = sum([cirq.Z(q) for q in qubits])
    param_resolver = cirq.ParamResolver({'a': 1})
    a = sympy.Symbol('a')
    circuit = cirq.Circuit(
        [cirq.X(q) ** a for q in qubits] +
        [cirq.measure(q) for q in qubits]
    )

    client = floq.client.CirqClient("my_api_key")
    result = client.simulator.simulate_expectation_values(
        circuit, magnetization_op, param_resolvers
    )
    print(result)

Jobs queue manager
------------------

Floq client also provides an interface for inspecting and flushing pending jobs
queue. Each time a quantum circuit is submitted to the cloud, the Floq service
replies with unique job id and the job is queued for the execution.

::

    import floq.client

    client = floq.client.CirqClient("my_api_key")

    # Get pending jobs
    client.jobs_queue.print_pending_jobs()

    # Flush queue
    client.jobs_queue.flush()

TPU worker manager
------------------

Each individual API key is bound to dedicated TPU worker running in the cloud.
The Floq Client provides an interace for starting, stopping or restarting the
worker (in case it enters into some unexpected state). Additionally, you can
always check current worker status.

::

    import floq.client

    client = floq.client.CirqClient("my_api_key")

    # Start worker
    client.tpu_worker.start()

    # Get worker status
    print(client.tpu_worker.status())

    # Stop worker
    client.tpu_worker.stop()


More examples
-------------

Check out `samples`_ directory for Jupyter Notebooks and more code examples.
