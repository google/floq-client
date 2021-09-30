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
import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="floq-client",
    version="0.1.5",
    author="Floq Team",
    author_email="floq-devs@google.com",
    description="Floq Service client",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_namespace_packages(),
    install_requires=[
        "cirq==0.11.0",
        "dependency-injector>=4.20.2",
        "marshmallow>=3.10.0",
        "marshmallow-dataclass>=8.3.1",
        "marshmallow-enum>=1.5.1",
        "progressbar2>=3.53.1",
        "requests>=2.24.0",
        "typeguard>=2.12.1",
    ],
    extras_require={
        "docs": [
            "sphinx-rtd-theme>=0.5.2",
            "sphinx>=4.1.2",
            "sphinxcontrib-napoleon>=0.7",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    entry_points={
        "console_scripts": ["floq-client=scripts.cli:main"],
    },
)
