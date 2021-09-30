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
"""This module provides interfaces for sending quantum circuits to the Floq
service."""

import abc
import os
import uuid
import threading
from typing import Any, List, Optional, Type, Union, cast
import cirq
import marshmallow
import progressbar

from .. import api_client, errors, schemas, sse


JobContext = Union[
    Type[schemas.JobContext],
    Type[schemas.BatchJobContext],
    Type[schemas.SweepJobContext],
]


class SimulationProgressThread(threading.Thread):
    """Displays simulation job progress status.

    This class uses `progressbar.ProgressBar` to display simulation job
    progress. Every time the Floq service finish simulating a work item it sends
    a status event. Between events we need to manually force refresh the bar to
    update elapsed timer widget.
    """

    def __init__(self, size: int) -> None:
        """Creates SimulationProgressThread class instance.

        Args:
            size: Total number of work items (as determined by Floq service).
        """
        super().__init__()
        self._bar = progressbar.ProgressBar(
            max_value=size,
            poll_interval=1,
            widgets=[
                "Processing submitted job ",
                progressbar.Bar(),
                " ",
                progressbar.Percentage(),
                " | ",
                progressbar.Timer(),
            ],
        )
        self._event = threading.Event()

    def run(self) -> None:
        """See base class documentation."""
        self._bar.start()
        while not self._event.is_set():
            self._bar.update(self._bar.value, force=True)
            self._event.wait(1)

    def finalize(self) -> None:
        """Finalizes the thread.

        Stops thread main loop and sends notification to the progress bar.
        """
        self._event.set()
        self._bar.finish()

    def update(self, current: int, total: int) -> None:
        """Sets a new progress value.

        Args:
            current: Number of completed work items.
            total: Total number of work items.
        """
        if total != self._bar.max_value:
            self._bar.max_value = total

        self._bar.update(current)


class AbstractRemoteSimulator(
    abc.ABC
):  # pylint: disable=too-few-public-methods
    """An abstract remote simulator.

    This class contains core logic for sending simulation job context to the
    Floq service and fetching job results. The subclass, which provides concrete
    job type specialization, must implement its own :meth:`run` method that
    reflects cirq specific simulator.
    """

    def __init__(
        self,
        client: api_client.ApiClient,
        handler: sse.EventStreamHandler,
        endpoint: str,
        schema: marshmallow.Schema,
    ) -> None:
        """Creates AbstractRemoteSimulator class instance.

        Args:
            client: Reference to ApiClient object.
            handler: Reference to EventStreamHandler object.
            endpoint: Job specific API endpoint.
            schema: Schema to be used for decoding JSON encoded job results.
        """
        self._base_url = f"jobs/{endpoint}"
        self._client = client
        self._handler = handler

        self._progress_thread: Optional[SimulationProgressThread] = None

        self._job_result: Optional[Any] = None
        self._results_schema = schema

    @abc.abstractmethod
    def run(self, *args, **kwargs) -> Any:
        """Runs a simulation.

        Returns:
            Simulation result.
        """

    def _finalize_progress_thread(self) -> None:
        """Finalizes progress thread."""
        self._progress_thread.finalize()
        self._progress_thread.join(timeout=5)
        self._progress_thread = None

    def _on_job_result(
        self,
        event: schemas.JobStatusEvent,
        _context: Optional[Any],
    ) -> None:
        """Callaback function triggered after receiving a job execution progress
        event.

        Args:
            event: Received event.
            context: Optional user context data passed together with the event.
        """
        if event.data.status == schemas.JobStatus.NOT_STARTED:
            return

        if event.data.status == schemas.JobStatus.IN_PROGRESS:
            if not self._progress_thread:
                self._progress_thread = SimulationProgressThread(
                    event.data.progress.total
                )
                self._progress_thread.start()
            else:
                self._progress_thread.update(
                    event.data.progress.completed, event.data.progress.total
                )
            return

        self._finalize_progress_thread()

        if event.data.status == schemas.JobStatus.ERROR:
            raise errors.SimulationError(
                cast(uuid.UUID, event.data.id),
                cast(str, event.data.error_message),
            )

        if event.data.status == schemas.JobStatus.COMPLETE:
            self._job_result = event.data.result

    def _submit_job(self, context: str, url: str) -> Any:
        """Submits job to the service and opens job status event stream.

        Args:
            context: Simulation job context.
            url: Target Floq service endpoint.

        Returns:
            Simulation job result.
        """
        response = self._client.post(url, context)
        data: schemas.JobSubmitted = schemas.decode(
            schemas.JobSubmittedSchema, response.text
        )

        self._job_result = None
        url = os.path.join(self._base_url, str(data.id), "stream")

        try:
            self._handler.open_stream(url, self._on_job_result)
        except Exception as error:
            if self._progress_thread:
                self._finalize_progress_thread()

            raise error

        return self._job_result

    def _url_for_context(self, context: JobContext) -> str:
        """Gets job URL endpoint for given job context.

        Args:
            context: Input job context.

        Returns:
            URL endpoint.
        """
        url = self._base_url
        if isinstance(context, schemas.BatchJobContext):
            url = os.path.join(url, "batch")
        elif isinstance(context, schemas.SweepJobContext):
            url = os.path.join(url, "sweep")

        return os.path.join(url, "submit")


class SamplesSimulator(
    AbstractRemoteSimulator
):  # pylint: disable=too-few-public-methods
    """Samples remote simulator."""

    def __init__(
        self,
        client: api_client.ApiClient,
        handler: sse.SampleJobStatusStreamHandler,
    ) -> None:
        """Creates SamplesSimulator class instance.

        Args:
            client: Reference to ApiClient object.
            handler: Reference to SampleJobStatusStreamHandler object.
        """
        super().__init__(
            client, handler, "sample", schemas.SampleJobResultSchema
        )

    # pylint: disable=arguments-differ
    def run(  # type: ignore
        self,
        circuit: cirq.circuits.Circuit,
        param_resolver: cirq.study.ParamResolver,
        repetitions: int,
    ) -> cirq.Result:
        """Runs a simulation.

        Args:
            circuit: The circuit to simulate.
            param_resolver: Parameters to run with the program.
            repetitions: Number of times to repeat the run. It is expected that
                this is greater than 0.

        Returns:
            A `cirq.Result` object.
        """
        try:
            data = schemas.SampleJobContext(
                circuit=circuit,
                param_resolver=param_resolver,
                repetitions=repetitions,
            )
            serialized_data = schemas.encode(
                schemas.SampleJobContextSchema,
                data,
            )
        except Exception as ex:
            raise errors.SerializationError from ex

        url = self._url_for_context(data)
        results: cirq.Result = self._submit_job(serialized_data, url)
        return results

    def run_sweep(
        self,
        circuit: cirq.circuits.Circuit,
        params: cirq.study.Sweepable,
        repetitions: int,
    ) -> List[cirq.Result]:
        """Runs a simulation.

        Args:
            circuit: The circuit to simulate.
            param_resolver: Parameters to run with the program.
            repetitions: Number of times to repeat the run. It is expected that
                this is greater than 0.

        Returns:
            List of `cirq.Result` objects.
        """
        try:
            data = schemas.SampleSweepJobContext(
                circuit=circuit,
                params=params,
                repetitions=repetitions,
            )
            serialized_data = schemas.encode(
                schemas.SampleSweepJobContextSchema,
                data,
            )
        except Exception as ex:
            raise errors.SerializationError from ex

        url = self._url_for_context(data)
        results: List[cirq.Result] = self._submit_job(serialized_data, url)
        return results

    def run_batch(
        self,
        circuits: List[cirq.circuits.Circuit],
        params: List[cirq.study.Sweepable],
        repetitions: Union[int, List[int]],
    ) -> List[List[cirq.Result]]:
        """Runs a simulation.

        Args:
            circuit: The circuit to simulate.
            param_resolver: Parameters to run with the program.
            repetitions: Number of times to repeat the run. It is expected that
                this is greater than 0.

        Returns:
            List of lists of `cirq.Result` objects. The outer list corresponds
            to each circuit submitted and and the inner list corresponds to each
            parameter set generated from the Sweepable submitted for that
            circuit.
        """
        try:
            data = schemas.SampleBatchJobContext(
                circuits=circuits,
                params=params,
                repetitions=repetitions,
            )
            serialized_data = schemas.encode(
                schemas.SampleBatchJobContextSchema,
                data,
            )
        except Exception as ex:
            raise errors.SerializationError from ex

        url = self._url_for_context(data)
        results: List[List[cirq.Result]] = self._submit_job(
            serialized_data, url
        )
        return results


class ExpectationValuesSimulator(
    AbstractRemoteSimulator
):  # pylint: disable=too-few-public-methods
    """Expectations values remote simulator."""

    def __init__(
        self,
        client: api_client.ApiClient,
        handler: sse.ExpectationJobStatusStreamHandler,
    ) -> None:
        """Creates ExpectationValuesSimulator class instance.

        Args:
            client: Reference to ApiClient object.
            handler: Reference to ExpectationJobStatusStreamHandler object.
        """
        super().__init__(
            client, handler, "exp", schemas.ExpectationJobResultSchema
        )

    # pylint: disable=arguments-differ
    def run(  # type: ignore
        self,
        circuit: cirq.circuits.Circuit,
        param_resolver: cirq.study.ParamResolver,
        observables: schemas.OperatorsType,
    ) -> List[float]:
        """Runs a simulation.

        Args:
            circuit: The circuit to simulate.
            param_resolver: Parameters to run with the program.
            observables: PauliSums to compute expectations against.

        Returns:
            A list of expectation values, with the value at index `n`
            corresponding to `observables[n]` from the input.
        """
        try:
            data = schemas.ExpectationJobContext(
                circuit=circuit,
                param_resolver=param_resolver,
                operators=observables,
            )
            serialized_data = schemas.encode(
                schemas.ExpectationJobContextSchema,
                data,
            )
        except Exception as ex:
            raise errors.SerializationError from ex

        url = self._url_for_context(data)
        return self._submit_job(serialized_data, url)

    def run_sweep(
        self,
        circuit: cirq.circuits.Circuit,
        params: cirq.study.Sweepable,
        observables: schemas.OperatorsType,
    ) -> List[List[float]]:
        """Runs a simulation.

        Args:
            circuit: The circuit to simulate.
            param_resolver: Parameters to run with the program.
            observables:  PauliSums to compute expectations against.

        Returns:
            A list of lists of expectation values. The outer list corresponds to
            the parameter set generated from the Sweepable, and the inner list
            corresponds to each observable provided.
        """
        try:
            data = schemas.ExpectationSweepJobContext(
                circuit=circuit,
                params=params,
                operators=observables,
            )
            serialized_data = schemas.encode(
                schemas.ExpectationSweepJobContextSchema,
                data,
            )
        except Exception as ex:
            raise errors.SerializationError from ex

        url = self._url_for_context(data)
        results: List[List[float]] = self._submit_job(serialized_data, url)
        return results

    def run_batch(
        self,
        circuits: List[cirq.circuits.Circuit],
        params: List[cirq.study.Sweepable],
        observables: List[schemas.OperatorsType],
    ) -> List[List[List[float]]]:
        """Runs a simulation.

        Args:
            circuit: The circuit to simulate.
            param_resolver: Parameters to run with the program. One sweepable
                per circuit.
            observables:  List of PauliSums to compute expectations against. One
                List of PauliSums per circuit.

        Returns:
            A list of lists of lists of expectation values. The outer list
            corresponds to the circuit, the middle list corresponds to the
            parameter set generated from the Sweepable for that circuit, and the
            inner list corresponds to each observable provided for that circuit.
        """
        try:
            data = schemas.ExpectationBatchJobContext(
                circuits=circuits,
                params=params,
                operators=observables,
            )
            serialized_data = schemas.encode(
                schemas.ExpectationBatchJobContextSchema,
                data,
            )
        except Exception as ex:
            raise errors.SerializationError from ex

        url = self._url_for_context(data)
        results: List[cirq.Result] = self._submit_job(serialized_data, url)
        return results
