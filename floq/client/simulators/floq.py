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
import time
import uuid
from typing import Any, Dict, List, Optional, cast
import cirq
import marshmallow
import numpy as np

from .. import api_client, errors, schemas


class AbstractRemoteSimulator(abc.ABC):
    """An abstract remote simulator.

    This class contains core logic for sending simulation job context to the
    Floq service and polling job results. The subclass, which provides concrete
    job type specialization, must implement its own run() method that reflects
    Cirq specific simulator.
    """

    _BACKOFF_SECONDS = [0, 1, 1, 2, 3, 5, 8, 13, 21]
    _TIMEOUT = 300  # 5 minutes

    def __init__(
        self,
        client: api_client.ApiClient,
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
        # Last submitted job id
        self._job_id: Optional[uuid.UUID] = None
        self._results_schema = schema

    def resume_polling(self, timeout: int = _TIMEOUT) -> Any:
        """Resumes job pooling.

        If the previous polling attempt failed due to TimeoutError, calling this
        function will result in resuming polling until job finished execution.

        Args:
            timeout: Maximum number of seconds to wait for simulation to
            complete.

        Raises:
            ResumePollingError if no job have been previously queried.
            SimulationError if the job failed.
            TimeoutError if the job has not finished within given time limit.
        """
        if not self._job_id:
            raise errors.ResumePollingError()

        return self._poll_results(timeout)

    @abc.abstractmethod
    def run(self, *args, **kwargs) -> Any:
        """Runs a simulation.

        Returns:
            Simulation result.
        """

    def _poll_results(self, timeout: int = _TIMEOUT) -> Any:
        """Polls simulation result.

        Args:
            timeout: Maximum number of seconds to wait for simulation to
            complete.

        Returns:
            Simulation job result.

        Raises:
            SimulationError if the job failed.
            TimeoutError if the job has not finished within given time limit.
        """
        url = os.path.join(self._base_url, str(self._job_id), "results")

        generator = (x for x in self._BACKOFF_SECONDS)
        deadline = time.time() + timeout
        while time.time() < deadline:
            response = self._client.get(url)
            result: schemas.JobResult = schemas.decode(
                self._results_schema, response.text
            )

            if result.status in (
                schemas.JobStatus.ERROR,
                schemas.JobStatus.COMPLETE,
            ):
                self._job_id = None

            if result.status == schemas.JobStatus.ERROR:
                raise errors.SimulationError(
                    cast(uuid.UUID, self._job_id),
                    cast(str, result.error_message),
                )

            if result.status == schemas.JobStatus.COMPLETE:
                return result.result

            backoff_time = next(generator, self._BACKOFF_SECONDS[-1])
            time.sleep(backoff_time)

        raise errors.PollingTimeoutError(cast(uuid.UUID, self._job_id))

    def _submit_job(self, context: str) -> uuid.UUID:
        """Submits job to the service.

        Args:
            context: Simulation job context.

        Returns:
            Unique job id.
        """
        url = os.path.join(self._base_url, "submit")
        response = self._client.post(url, context)
        data: schemas.JobSubmitted = schemas.decode(
            schemas.JobSubmittedSchema, response.text
        )
        return data.id

    def _submit_and_poll(self, context: str) -> Any:
        """Submits job to the service and polls for the results.

        Args:
            context: Simulation job context.

        Returns:
            Simulation job result.
        """
        self._job_id = self._submit_job(context)
        return self._poll_results()


class SamplesSimulator(AbstractRemoteSimulator):
    """Samples remote simulator."""

    def __init__(self, client: api_client.ApiClient) -> None:
        """Creates SamplesSimulator class instance.

        Args:
            client: Reference to ApiClient object.
        """
        super().__init__(client, "sample", schemas.SampleJobResultSchema)

    def run(
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

        results: cirq.study.TrialResult = self._submit_and_poll(serialized_data)
        return results._measurements


class ExpectationValuesSimulator(AbstractRemoteSimulator):
    """Expectations values remote simulator."""

    def __init__(self, client: api_client.ApiClient) -> None:
        """Creates ExpectationValuesSimulator class instance.

        Args:
            client: Reference to ApiClient object.
        """
        super().__init__(client, "exp", schemas.ExpectationJobResultSchema)

    def run(
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

        return self._submit_and_poll(serialized_data)
