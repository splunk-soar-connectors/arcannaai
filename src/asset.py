# Copyright (c) 2026 Splunk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the License for the specific language governing permissions
# and limitations under the License.

from soar_sdk.asset import AssetField, BaseAsset, FieldCategory

from .consts import DEFAULT_TIMEOUT


class Asset(BaseAsset):
    base_url: str = AssetField(
        description="Arcanna.ai API base URL (for example https://arcanna.example.com)",
        category=FieldCategory.CONNECTIVITY,
    )
    api_key: str = AssetField(
        description="Arcanna API key (sent as the x-arcanna-api-key header)",
        sensitive=True,
        category=FieldCategory.CONNECTIVITY,
    )
    verify_server_cert: bool | None = AssetField(
        description="Verify the server TLS certificate",
        default=True,
        category=FieldCategory.CONNECTIVITY,
    )
    default_job_id: float | None = AssetField(
        description="Default Arcanna job id used when an action is run without one",
        category=FieldCategory.ACTION,
    )
    default_storage_name: str | None = AssetField(
        description=(
            "Storage name (or storage tag) of the job's REST input, used when an action is run without one; "
            "needed when the API key reaches several storages of a job"
        ),
        category=FieldCategory.ACTION,
    )
    timeout: float | None = AssetField(
        description="HTTP timeout in seconds",
        default=DEFAULT_TIMEOUT,
        category=FieldCategory.CONNECTIVITY,
    )
