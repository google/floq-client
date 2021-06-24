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
"""Components dependencies structure.

Rather than manually creating class objects we are using dependency-injector
framework to declare components dependencies (containers) and let the
library do the work for us.

Our structure is declared using few independent containers:
  - Core container contains core components that are being used by other
    classes.
  - Managers container provides clients for managing Floq service resources.
  - Simulators container is dedicated for creating Floq service simulators
  - Client container connects all containers together.
"""

# pylint: disable=c-extension-no-member, import-error, too-few-public-methods

import dependency_injector.containers
import dependency_injector.providers

from . import api_client, jobs_queue, schemas, simulators, sse, worker


class Core(dependency_injector.containers.DeclarativeContainer):
    """Floq client core components."""

    config = dependency_injector.providers.Configuration(strict=True)

    ApiClient = dependency_injector.providers.Singleton(
        api_client.ApiClient,
        hostname=config.hostname,
        api_key=config.api_key,
        use_ssl=config.use_ssl,
    )
    TaskStatusStreamHandler = dependency_injector.providers.Factory(
        sse.TaskStatusStreamHandler, client=ApiClient
    )


class Managers(dependency_injector.containers.DeclarativeContainer):
    """Floq API resources managers."""

    core = dependency_injector.providers.DependenciesContainer()

    JobsQueueManager = dependency_injector.providers.Factory(
        jobs_queue.JobsQueueManager,
        client=core.ApiClient,
        handler=core.TaskStatusStreamHandler,
    )
    WorkerManager = dependency_injector.providers.Factory(
        worker.WorkerManager,
        client=core.ApiClient,
        handler=core.TaskStatusStreamHandler,
    )


class Simulators(dependency_injector.containers.DeclarativeContainer):
    """Floq remote simulators."""

    core = dependency_injector.providers.DependenciesContainer()

    remote_simulators = dependency_injector.providers.Dict(
        {
            schemas.JobType.EXPECTATION: dependency_injector.providers.Factory(
                simulators.ExpectationValuesSimulator, client=core.ApiClient
            ),
            schemas.JobType.SAMPLE: dependency_injector.providers.Factory(
                simulators.SamplesSimulator, client=core.ApiClient
            ),
        }
    )

    CirqSimulator = dependency_injector.providers.Factory(
        simulators.CirqSimulator, simulators=remote_simulators
    )


class Client(dependency_injector.containers.DeclarativeContainer):
    """Floq client main container."""

    core = dependency_injector.providers.Container(Core)
    managers = dependency_injector.providers.Container(Managers, core=core)
    simulators = dependency_injector.providers.Container(
        Simulators, core=core
    )
