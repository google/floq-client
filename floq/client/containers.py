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
"""This module provides components dependencies structure.

.. _dependency-injector:
   https://python-dependency-injector.ets-labs.org/

Rather than manually creating class objects we are using `dependency-injector`_
framework to declare components dependencies (containers) and let the library
do the work for us.

Our structure is declared using following containers:

- :class:`.Core` container contains core components that are being used by other
  classes.
- :class:`.Managers` container provides clients for managing Floq service
  resources.
- :class:`.Simulators` container is dedicated for creating Floq service
  simulators.
- :class:`.Client` container connects all containers together.
"""

# pylint: disable=c-extension-no-member, import-error, too-few-public-methods

import dependency_injector.containers
import dependency_injector.providers

from . import api_client, jobs_queue, schemas, simulators, sse, worker


class Core(dependency_injector.containers.DeclarativeContainer):
    """Floq client core components."""

    #: Client configuration provider.
    config = dependency_injector.providers.Configuration(strict=True)

    #: :class:`floq.client.api_client.ApiClient` class provider.
    ApiClient = dependency_injector.providers.Singleton(
        api_client.ApiClient,
        hostname=config.hostname,
        api_key=config.api_key,
        use_ssl=config.use_ssl,
    )

    #: :class:`floq.client.sse.TaskStatusStreamHandler` class provider.
    TaskStatusStreamHandler = dependency_injector.providers.Factory(
        sse.TaskStatusStreamHandler, client=ApiClient
    )


class Managers(dependency_injector.containers.DeclarativeContainer):
    """Floq service resources managers."""

    #: Reference to :class:`Core` container.
    core = dependency_injector.providers.DependenciesContainer()

    #: :class:`floq.client.jobs_queue.JobsQueueManager` class provider.
    JobsQueueManager = dependency_injector.providers.Factory(
        jobs_queue.JobsQueueManager,
        client=core.ApiClient,
        handler=core.TaskStatusStreamHandler,
    )
    #: :class:`floq.client.worker.WorkerManager` class provider.
    WorkerManager = dependency_injector.providers.Factory(
        worker.WorkerManager,
        client=core.ApiClient,
        handler=core.TaskStatusStreamHandler,
    )


class Simulators(dependency_injector.containers.DeclarativeContainer):
    """Floq remote simulators."""

    #: Reference to :class:`Core` container.
    core = dependency_injector.providers.DependenciesContainer()

    #: Map of remote simulators provider.
    remote_simulators = dependency_injector.providers.Dict(
        {
            schemas.JobType.EXPECTATION: dependency_injector.providers.Factory(
                simulators.ExpectationValuesSimulator,
                client=core.ApiClient,
                handler=dependency_injector.providers.Factory(
                    sse.ExpectationJobStatusStreamHandler, client=core.ApiClient
                ),
            ),
            schemas.JobType.SAMPLE: dependency_injector.providers.Factory(
                simulators.SamplesSimulator,
                client=core.ApiClient,
                handler=dependency_injector.providers.Factory(
                    sse.SampleJobStatusStreamHandler, client=core.ApiClient
                ),
            ),
        }
    )

    #: :class:`floq.client.simulators.CirqSimulator` class provider.
    CirqSimulator = dependency_injector.providers.Factory(
        simulators.CirqSimulator, simulators=remote_simulators
    )


class Client(dependency_injector.containers.DeclarativeContainer):
    """Floq client main container."""

    #: Reference to :class:`Core` container.
    core = dependency_injector.providers.Container(Core)
    #: Reference to :class:`Managers` container
    managers = dependency_injector.providers.Container(Managers, core=core)
    #: Reference to :class:`Simulators` container
    simulators = dependency_injector.providers.Container(Simulators, core=core)
