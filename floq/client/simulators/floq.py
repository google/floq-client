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
"""Floq API based quantum circuits simulators.

This module defines Floq Client that submits quantum circuit simulation
requests to the cloud service and polls for the job results.
"""

import abc
import os
import uuid
from typing import Any, Dict, List, Optional, cast
import cirq
import marshmallow
import numpy as np

from .. import api_client, errors, schemas, sse


class AbstractRemoteSimulator(
    abc.ABC
):  # pylint: disable=too-few-public-methods
    """An abstract remote simulator.

    This class contains core logic for sending simulation job context to the
    Floq service and polling job results. The subclass, which provides concrete
    job type specialization, must implement its own run() method that reflects
    Cirq specific simulator.
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
            endpoint: Job specific REST API endpoint.
            schema: marshmallow schema to be used for decoding JSON encoded
            JobResult type object.
        """
        self._base_url = f"jobs/{endpoint}"
        self._client = client
        self._handler = handler
        # Last submitted job id
        self._job_id: Optional[uuid.UUID] = None
        self._job_result: Optional[Any] = None
        self._results_schema = schema

    @abc.abstractmethod
    def run(self, *args, **kwargs) -> Any:
        """Runs a simulation.

        Returns:
            Simulation result.
        """

    def _on_job_result(
        self,
        event: schemas.JobStatusEvent,
        _context: Optional[Any],
    ) -> None:
        """Callaback function triggered after receiving a job execution progress
        event.

        Args:
            event: Received event.
            context: Optional user context data passed together with the
            event.
        """
        if event.data.status not in (
            schemas.JobStatus.COMPLETE,
            schemas.JobStatus.ERROR,
        ):
            return

        if event.data.status == schemas.JobStatus.ERROR:
            raise errors.SimulationError(
                cast(uuid.UUID, self._job_id),
                cast(str, event.data.error_message),
            )

        if event.data.status == schemas.JobStatus.COMPLETE:
            self._job_result = event.data.result

    def _submit_job(self, context: str) -> Any:
        """Submits job to the service and opens job status event stream.

        Args:
            context: Simulation job context.

        Returns:
            Simulation job result.
        """
        url = os.path.join(self._base_url, "submit")
        response = self._client.post(url, context)
        data: schemas.JobSubmitted = schemas.decode(
            schemas.JobSubmittedSchema, response.text
        )

        self._job_result = None
        url = os.path.join(self._base_url, str(data.id), "stream")
        self._handler.open_stream(url, self._on_job_result)

        return self._job_result


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
    ) -> Dict[str, np.ndarray]:
        """Runs a simulation.

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

        results: cirq.study.TrialResult = self._submit_job(serialized_data)
        return results._measurements  # pylint: disable=protected-access


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
            repetitions: An observable or list of observables.

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

        return self._submit_job(serialized_data)
