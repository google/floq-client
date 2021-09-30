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
"""This module provides Floq client errors."""
import uuid


class FloqError(Exception):
    """Generic Floq exception.

    All Floq client errors extend this error class.
    """


class SerializationError(FloqError):
    """`cirq` serialization error."""

    def __init__(self) -> None:
        """Creates SerializationError class instance."""
        super().__init__("cirq encountered a serialization error.")


class ServiceError(FloqError):
    """Floq service serror.

    Attributes:
        message (int): User friendly API error message.
        status_code (str): HTTP error code.
    """

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
    """Simulation error.

    Attributes:
        job_id (uuid.UUID): Unique job id.
        message (str): User friendly message explaining why the job failed.
    """

    def __init__(self, job_id: uuid.UUID, message: str) -> None:
        """Creates SimulationError class instance.

        Args:
            job_id: Unique job id.
            message: Simulation error message.
        """
        super().__init__(
            f"Simulation job {str(job_id)} failed with message: {message}"
        )
        self.job_id = job_id
        self.message = message
