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
"""Floq client errors."""
import uuid


class FloqError(Exception):
    """Generic Floq exception."""


class ResumePollingError(FloqError):
    """Resume polling error."""

    def __init__(self) -> None:
        """Creates ResumePollingError class instance."""
        super().__init__("No jobs have been previously queried")


class SerializationError(FloqError):
    """Cirq serialization error."""

    def __init__(self) -> None:
        """Creates SerializationError class instance."""
        super().__init__(
            """
Cirq encountered a serialization error. This may be due to passing gates
parameterized on more than one symbol, which Cirq currently does not support.
Because Cirq rx, ry, and rz gates depend on an implicit internal symbol they can
fail. This is actively being resolved!

In the meantime try using XPow, YPow, ZPow gates instead:
    cirq.rx(s) -> cirq.XPowGate(exponent=(s/np.pi), global_shift=-0.5)
"""
        )


class ServiceError(FloqError):
    """Generic API service exception."""

    def __init__(self, status_code: int, message: str) -> None:
        """Creates ServiceError class instance.

        Args:
            status_code: HTTP error code.
            message: API error message.
        """
        super().__init__(f"API service error: {message}")
        self.message = message
        self.status_code = status_code


class SimulationError(FloqError):
    """Simulation job error."""

    def __init__(self, job_id: uuid.UUID, message: str) -> None:
        """Creates SimulationError class instance.

        Args:
            job_id: Unique job id.
            message: Simulation error message.
        """
        super().__init__(f"Simulation job {str(job_id)} failed with message:"
                         f" {message}")
        self.job_id = job_id
        self.message = message


class PollingTimeoutError(FloqError):
    """Simulation job result polling timeout."""

    def __init__(self, job_id: uuid.UUID) -> None:
        """Creates PollingTimeoutError class instance.

        Args:
            job_id:
        """
        super().__init__(
            f"Reached maximum timeout while polling job {str(job_id)} result."
            " Call the resume_polling() method to resume polling."
        )
        self.job_id = job_id
