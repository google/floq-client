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
# pylint: disable=protected-access,too-few-public-methods

"""Floq service CLI client."""
import abc
import argparse
import enum
from typing import Any, Sequence, Type, Union, cast

import floq.client
from floq.client import schemas


class AbstractServiceClient(abc.ABC):
    """Abstract class handling Floq service requests."""

    class CommandAction(argparse.Action):
        """Transforms raw string into enum."""

        def __init__(self, clazz: Type[enum.Enum], *args, **kwargs) -> None:
            """Creates CommandAction class instance.

            Transforms raw string command value into Enum type.

            Args:
                clazz: Target Enum class.
            """
            super().__init__(*args, **kwargs)
            self._enum_class = clazz

        def __call__(
            self,
            _parser: argparse.ArgumentParser,
            namespace: argparse.Namespace,
            values: Union[str, Sequence[Any], None],
            _option_string: Union[str, Sequence[Any], None] = None,
        ) -> None:
            setattr(
                namespace,
                self.dest,
                self._enum_class[cast(str, values).upper()],
            )

    def __init__(self, api_key: str) -> None:
        """Creates AbstractServiceClient class instance.

        Args:
            api_key: Floq service API key.
        """
        self._client = floq.client.CirqClient(api_key)

    @classmethod
    @abc.abstractmethod
    def add_subparser(cls, parser: argparse._SubParsersAction) -> None:
        """Adds resource specific ArgumentParser to the parent parser.

        Args:
            parser: Reference to parent ArgumentParser class object.
        """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Resource name."""

    @abc.abstractmethod
    def handle_command(self, command: Any) -> None:
        """Handles Floq service command.

        Args:
            command: Service command.
        """


class JobsQueueClient(AbstractServiceClient):
    """Handles jobs queue requests."""

    name = "jobs"

    class Command(enum.IntEnum):
        """Supported jobs queue commands."""

        DISPLAY = enum.auto()
        FLUSH = enum.auto()

    class CommandAction(AbstractServiceClient.CommandAction):
        """Transforms raw command string into Command enum."""

        def __init__(self, *args, **kwargs) -> None:
            """Creates CommandAction class instance."""
            super().__init__(JobsQueueClient.Command, *args, **kwargs)

    @classmethod
    def add_subparser(cls, parser: argparse._SubParsersAction) -> None:
        subparser = parser.add_parser(
            cls.name, help="Controls and inspects jobs queue"
        )
        subparser.add_argument(
            "command",
            help="Jobs queue command",
            type=str,
            action=cls.CommandAction,
            choices=[x.name.lower() for x in cls.Command],
        )

    def handle_command(self, command: Command) -> None:
        if command == self.Command.DISPLAY:
            self._handle_display_queue()
        elif command == self.Command.FLUSH:
            self._handle_flush_queue()

    def _handle_display_queue(self) -> None:
        """Handles display jobs queue command.

        Fetches pending jobs queue and details about every single job in the
        queue.
        """
        buffer = []
        for idx, job_id in enumerate(self._client.jobs_queue.get().ids):
            job = self._client.jobs_queue.get_pending_job(job_id)
            buffer.append(
                f"idx: {idx}, id: {str(job.id)}, type: {job.type.name},"
                f" status: {job.status.name}"
            )

        if len(buffer) == 0:
            print("Jobs queue is empty")
            return

        for line in buffer:
            print(line)

    def _handle_flush_queue(self) -> None:
        """Handles flush jobs queue command."""
        self._client.jobs_queue.flush()


class TPUWorkerClient(AbstractServiceClient):
    """Handles TPU worker requests."""

    name = "worker"

    class Command(enum.IntEnum):
        """Supported TPU workers commands."""

        RESTART = enum.auto()
        START = enum.auto()
        STATUS = enum.auto()
        STOP = enum.auto()

    class CommandAction(AbstractServiceClient.CommandAction):
        """Transforms raw command string into Command enum."""

        def __init__(self, *args, **kwargs) -> None:
            """Creates CommandAction class instance."""
            super().__init__(TPUWorkerClient.Command, *args, **kwargs)

    @classmethod
    def add_subparser(cls, parser: argparse._SubParsersAction) -> None:
        subparser = parser.add_parser(
            cls.name, help="Controls and displays status of TPU worker"
        )
        subparser.add_argument(
            "command",
            help="TPU worker command",
            type=str,
            action=cls.CommandAction,
            choices=[x.name.lower() for x in cls.Command],
        )

    def handle_command(self, command: Command) -> None:
        if command in (
            self.Command.RESTART,
            self.Command.START,
            self.Command.STOP,
        ):
            self._handle_start_stop(command)
        elif command == self.Command.STATUS:
            self._handle_worker_status()

    def _handle_start_stop(self, command: Command) -> None:
        """Handles START, STOP, RESTART worker commands.

        Args:
            command: Worker command.
        """
        worker = self._client.tpu_worker
        getattr(worker, command.name.lower())()

    def _handle_worker_status(self) -> None:
        """Handles worker status command."""
        status = self._client.tpu_worker.status()

        msg = f"Worker state: {status.state.name}"
        if status.state == schemas.WorkerState.PROCESSING_JOB:
            msg = f"{msg}, job id: {status.job_id}"
        elif status.state == schemas.WorkerState.ERROR:
            msg = f"{msg}: {status.error}"

        print(msg)


def main() -> None:
    """Script entry point."""
    resources = (JobsQueueClient, TPUWorkerClient)

    parser = argparse.ArgumentParser(
        "Floq CLI client",
        description="A helper script that controls Floq service resources.",
    )
    parser.add_argument("api_key", type=str, help="Floq service API key")

    subparser = parser.add_subparsers(
        title="resource",
        description="Floq service resource",
        dest="resource",
        required=True,
    )
    for resource in resources:
        resource.add_subparser(subparser)

    args = parser.parse_args()

    service = next((x for x in resources if x.name == args.resource))(
        args.api_key
    )
    service.handle_command(args.command)


if __name__ == "__main__":
    main()
