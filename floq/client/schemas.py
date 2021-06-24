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
"""Floq external marshamllow schemas.

This module defines common schemas that are being used for exchanging data
between API client, API service and TPU workers.
"""
import dataclasses
import enum
import json
import time
import typing
import cirq
import marshmallow
import marshmallow_dataclass
import marshmallow_enum


#####################################
# Utility functions                 #
#####################################


def decode(schema: marshmallow.Schema, data: str, **kwargs) -> dataclasses.dataclass:
    """Decodes input data using provided schema.

    Args:
        schema: Schema to be used for deserialization.
        data: JSON-encoded data to be deserialized.

    Returns:
        Deserialized dataclass object.
    """
    return schema.loads(data, **kwargs)


def encode(schema: marshmallow.Schema, data: dataclasses.dataclass, **kwargs) -> str:
    """Encodes input data using provided schema.

    Args:
        schema: Schema to be used for serialization.
        data: Dataclass object to be serialized.

    Returns:
        JSON-encoded serialized data.
    """
    return schema.dumps(data, separators=(",", ":"), **kwargs)


#####################################
# Types aliases                     #
#####################################


OperatorsType = typing.Union[cirq.ops.PauliSum, typing.List[cirq.ops.PauliSum]]


#####################################
# marshmallow helpers               #
#####################################

_SerializedCirqObject = typing.Dict[str, typing.Any]
_SerializedPauliSums = typing.List[typing.List[typing.Dict[str, typing.Any]]]

# `cirq` offers only functions to dump and load objects from the JSON encoded
# string, and does not support builtin dict objects. When we call json.dumps()
# over already JSON encoded string, all quotation marks and brackets are
# prefixed with the backslash.


def _deserialize_cirq_object(data: _SerializedCirqObject) -> typing.Any:
    """Deserializes cirq object from dict type.

    Since `cirq` does not provide function to load objects from builtin dict
    objects, we need some workaround here: first we dump the dict object into
    JSON encoded string, then parse them into `cirq` object.

    Args:
        data: Dict encoded cirq object.

    Returns:
        Deserialized cirq object.
    """
    return cirq.read_json(json_text=json.dumps(data))


def _serialize_cirq_object(obj: typing.Any) -> _SerializedCirqObject:
    """Serializes cirq object to dict type.

    Since `cirq` does not provide function to dump objects into builtin dict
    objects, we need some workaround here: first we dump the `cirq` object into
    JSON encoded string, then parsing them into dict object.

    Args:
        data: cirq object to be encoded.

    Returns:
        Serialized cirq object.
    """
    return json.loads(cirq.to_json(obj))


class _CirqField(marshmallow.fields.Field):
    """Field that serializes and deserializes cirq object."""

    def _serialize(self, value: typing.Any, *_args, **_kwargs) -> _SerializedCirqObject:
        """See base class documentation."""
        return _serialize_cirq_object(value)

    def _deserialize(
        self, value: _SerializedCirqObject, *_args, **_kwargs
    ) -> typing.Any:
        """See base class documentation."""
        try:
            return _deserialize_cirq_object(value)
        except json.JSONDecodeError as ex:
            raise marshmallow.ValidationError("Not a JSON object") from ex


class _OperatorsField(marshmallow.fields.Field):
    """Field that serializes and deserializes PauliSum operators."""

    def _serialize(
        self, value: OperatorsType, _attr, _obj, **kwargs
    ) -> _SerializedPauliSums:
        """See base class documentation."""
        if not isinstance(value, list):
            value = [value]

        return [[_serialize_cirq_object(term) for term in op] for op in value]

    def _deserialize(
        self, value: _SerializedPauliSums, _attr, _obj, **kwargs
    ) -> OperatorsType:
        """See base class documentation."""
        try:
            return [
                sum([_deserialize_cirq_object(term) for term in op]) for op in value
            ]
        except json.JSONDecodeError as ex:
            raise marshmallow.ValidationError("Not a JSON object") from ex


Circuit = marshmallow_dataclass.NewType("Circuit", cirq.Circuit, field=_CirqField)
Operators = marshmallow_dataclass.NewType(
    "Operators", OperatorsType, field=_OperatorsField
)
ParamResolver = marshmallow_dataclass.NewType(
    "ParamResolver", cirq.ParamResolver, field=_CirqField
)
Result = marshmallow_dataclass.NewType("Result", cirq.Result, field=_CirqField)


UUID = marshmallow_dataclass.NewType("UUID", str, field=marshmallow.fields.UUID)


#####################################
# API relevant types                #
#####################################


@dataclasses.dataclass
class APIError:
    """API error response data.

    Properties:
        code: HTTP error code.
        message: Error details.
    """

    code: int
    message: str


#####################################
# Jobs relevant types               #
#####################################


class JobStatus(enum.IntEnum):
    """Current job status."""

    NOT_STARTED = 0
    IN_PROGRESS = 1
    COMPLETE = 2
    ERROR = 3


class JobType(enum.IntEnum):
    """Simulation job type"""

    SAMPLE = 0
    EXPECTATION = 1


@dataclasses.dataclass
class JobsQueue:
    """Get job queue response data.

    Properties:
        ids: List of pending jobs ids.
    """

    ids: typing.List[UUID] = dataclasses.field(default_factory=[])


@dataclasses.dataclass
class PendingJob:
    """Get queued job response data.

    Properties:
        id: Unique job id.
        status: Current job status.
        type: Job type.
    """

    id: UUID  # pylint: disable=invalid-name
    status: JobStatus = dataclasses.field(
        metadata={
            "marshmallow_field": marshmallow_enum.EnumField(
                JobStatus,
                by_value=True,
            )
        }
    )
    type: JobType = dataclasses.field(
        metadata={
            "marshmallow_field": marshmallow_enum.EnumField(
                JobType,
                by_value=True,
            )
        }
    )

    def __post_init__(self) -> None:
        """See base class documentation."""
        if self.status in (JobStatus.COMPLETE, JobStatus.ERROR):
            raise ValueError(f"PendingJob cannot have {self.status.name} status")


@dataclasses.dataclass
class JobResult:
    """Get job results response data.

    Properties:
        id: Unique job id.
        result: Job result.
        status: Current job status.
    """

    id: UUID  # pylint: disable=invalid-name
    status: JobStatus = dataclasses.field(
        metadata={
            "marshmallow_field": marshmallow_enum.EnumField(
                JobStatus,
                by_value=True,
            )
        }
    )
    error_message: typing.Optional[str] = dataclasses.field(default=None)
    result: typing.Optional[typing.Any] = dataclasses.field(default=None)

    def __post_init__(self) -> None:
        """See base class documentation."""
        if self.status == JobStatus.ERROR:
            if not self.error_message:
                raise ValueError("Missing error messsage")
            if self.result:
                raise ValueError("Failed job cannot have result field")

        if self.status == JobStatus.COMPLETE:
            if not self.result:
                raise ValueError("Missing job result")
            if self.error_message:
                raise ValueError("Completed job cannot have error_message field")


@dataclasses.dataclass
class JobSubmitted:
    """Submit job response data.

    Properties:
        id: Unique job id.
    """

    id: UUID  # pylint: disable=invalid-name


@dataclasses.dataclass
class SubmitJobContext:
    """Submit job request data.

    Properties:
        circuit: Circuit to be run.
        param_resolver: ParamResolver to be used with the circuit.
    """

    circuit: Circuit
    param_resolver: ParamResolver


@dataclasses.dataclass
class ExpectationJobContext(SubmitJobContext):
    """Submit expectation job request data.

    Properties:
        circuit: Circuit to be run.
        operators: List of PauliSum operators.
        param_resolver: ParamResolver to be used with the circuit.
    """

    operators: Operators


@dataclasses.dataclass
class ExpectationJobResult(JobResult):
    """Get expectation job results response data.

    Properties:
        id: Unique job id.
        result: List of floats, same size as input operators size.
        status: Current job status.
    """

    result: typing.Optional[typing.List[float]] = dataclasses.field(default=None)


@dataclasses.dataclass
class SampleJobContext(SubmitJobContext):
    """Submit sample job request data.

    Properties:
        circuit: Circuit to be run.
        param_resolver: ParamResolver to be used with the circuit.
        repetitions: Number of times the circuit will run.
    """

    repetitions: int = dataclasses.field(default=1)


@dataclasses.dataclass
class SampleJobResult(JobResult):
    """Get sample job results response data.

    Properties:
        id: Unique job id.
        result: Output from running the circuit.
        status: Current job status.
    """

    result: typing.Optional[Result] = dataclasses.field(default=None)


#####################################
# Tasks relevant types              #
#####################################


class TaskState(enum.IntEnum):
    """Current task state."""

    PENDING = 0
    RUNNING = 1
    DONE = 2


@dataclasses.dataclass
class TaskStatus:
    """Current task status."""

    state: TaskState = dataclasses.field(
        metadata={
            "marshmallow_field": marshmallow_enum.EnumField(TaskState, by_value=True)
        }
    )
    error: typing.Optional[str] = dataclasses.field(default=None)
    success: typing.Optional[bool] = dataclasses.field(default=None)

    def __post_init__(self) -> None:
        """See base class documentation."""
        if self.state != TaskState.DONE and (
            (self.error is not None) or (self.success is not None)
        ):
            field = "error" if self.error is not None else "success"
            raise ValueError(f"Unfinished task cannot have {field} field.")


@dataclasses.dataclass
class TaskSubmitted:
    """Task requested response data.

    Properties:
        id: Unique task id.
    """

    id: UUID  # pylint: disable=invalid-name


#####################################
# Worker relevant types             #
#####################################


class WorkerState(enum.IntEnum):
    """TPU worker state."""

    OFFLINE = 0
    BOOTING = 1
    SHUTTING_DOWN = 2
    IDLE = 3
    PROCESSING_JOB = 4
    ERROR = 5


@dataclasses.dataclass
class Worker:
    """TPU worker current status.

    Properties:
        error: Error details.
        job_id: Currently processed job id.
        state: Worker state.
    """

    state: WorkerState = dataclasses.field(
        metadata={
            "marshmallow_field": marshmallow_enum.EnumField(WorkerState, by_value=True)
        }
    )
    error: typing.Optional[str] = dataclasses.field(default=None)
    job_id: typing.Optional[UUID] = dataclasses.field(default=None)

    def __post_init__(self) -> None:
        """See base class documentation."""
        if self.state not in (WorkerState.PROCESSING_JOB, WorkerState.ERROR) and (
            (self.error is not None) or (self.job_id is not None)
        ):
            raise ValueError(
                f"Cannot have extra properties for the worker status {self.state.name}"
            )

        if self.state == WorkerState.ERROR:
            if not self.error:
                raise ValueError("Missing error messsage")
            if self.job_id:
                raise ValueError("Cannot have job id field for the ERROR state")

        if self.state == WorkerState.PROCESSING_JOB:
            if not self.job_id:
                raise ValueError("Missing job id")
            if self.error:
                raise ValueError("Cannot have error message for the IDLE state")


#####################################
# Server side events                #
#####################################


@dataclasses.dataclass
class ServerSideEvent:
    """Base class for server side event.

    Properties:
        data: Event payload.
        event: Event name.
        id: Event unique id.
        timestamp: Event timestamp in UNIX seconds.
    """

    data: typing.Any
    event: str
    id: UUID  # pylint: disable=invalid-name
    timestamp: int = dataclasses.field(default=int(time.time()))


@dataclasses.dataclass
class TaskStatusEvent(ServerSideEvent):
    """Task status changed event.

    Properties:
        data: Task status.
        event: Event name.
        id: Task unique id.
    """

    data: TaskStatus


#####################################
# Schema Objects                    #
#####################################


class BaseSchema(marshmallow.Schema):
    """Base marshmallow schema for JobResult dataclass."""

    @marshmallow.post_dump
    def remove_empty_fields(  # pylint: disable=no-self-use
        self, data: typing.Dict, **_kwargs
    ) -> typing.Dict:
        """Removes all None fields from the input data.

        Args:
            data: Input data object.

        Returns:
            Filtered data.
        """

        return {k: v for k, v in data.items() if v is not None}


class SSERenderer:
    """A helper class for serializing and deserializing objects to server side
    events format."""

    @staticmethod
    def dumps(obj: typing.Dict[str, typing.Any], *_args, **_kwargs) -> str:
        """Encodes input object into text string.

        Args:
            obj: Object to be serialized.

        Returns:
            Text string in format:
              {key}: {value}\n
        """
        result = ""
        for key in ("event", "id", "timestamp", "data"):
            value = obj.get(key, None)
            if not value:
                continue

            if key == "data":
                value = json.dumps(value, separators=(",", ":"))

            result += f"{key}: {value}\n"

        result += "\n"
        return result

    @staticmethod
    def loads(  # pylint: disable=invalid-name
        s: str, *_args, **_kwargs
    ) -> typing.Dict[str, typing.Any]:
        """Decodes input text string into dict object.

        Args:
            s: Text string to be decoded.

        Returns:
            Dict object.
        """
        obj = {}
        for line in s.split("\n"):
            line = line.strip()
            if not line:
                continue

            key, value = line.split(": ")
            if key == "data":
                value = json.loads(value)

            obj[key] = value

        return obj


class SSEBaseSchema(BaseSchema):
    """Base marshmallow schema for server side events."""

    class Meta:  # pylint: disable=too-few-public-methods
        """See base class documentation."""

        render_module = SSERenderer


(
    APIErrorSchema,
    ExpectationJobContextSchema,
    ExpectationJobResultSchema,
    JobResultSchema,
    JobSubmittedSchema,
    JobsQueueSchema,
    PendingJobSchema,
    SampleJobContextSchema,
    SampleJobResultSchema,
    ServerSideEventSchema,
    SubmitJobContextSchema,
    TaskStatusSchema,
    TaskStatusEventSchema,
    TaskSubmittedSchema,
    WorkerSchema,
) = tuple(
    marshmallow_dataclass.class_schema(x, base_schema=y)()
    for x, y in (
        (APIError, None),
        (ExpectationJobContext, None),
        (ExpectationJobResult, BaseSchema),
        (JobResult, BaseSchema),
        (JobSubmitted, None),
        (JobsQueue, None),
        (PendingJob, None),
        (SampleJobContext, None),
        (SampleJobResult, BaseSchema),
        (ServerSideEvent, SSEBaseSchema),
        (SubmitJobContext, None),
        (TaskStatus, BaseSchema),
        (TaskStatusEvent, SSEBaseSchema),
        (TaskSubmitted, None),
        (Worker, BaseSchema),
    )
)
