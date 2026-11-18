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

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput, OutputField, PermissiveActionOutput
from soar_sdk.exceptions import ActionFailure
from soar_sdk.logging import getLogger
from soar_sdk.params import Params

from .. import consts
from ..asset import Asset
from ..client import ArcannaClient, rows

logger = getLogger()


class ScopeOutput(ActionOutput):
    scope: str = OutputField(column_name="Scope")


class PlatformMetricsOutput(PermissiveActionOutput):
    pass


class TotalScopesSummary(ActionOutput):
    total_scopes: int


def run_test_connectivity(soar: SOARClient, asset: Asset) -> None:
    logger.progress(consts.MSG_TEST_START)
    client = ArcannaClient(asset)
    # v2 health validates the key (401/403 otherwise) and answers {"request": {"status": "OK"}}
    health = client.get(consts.ENDPOINT_HEALTH)
    request = health.get("request") if isinstance(health, dict) else None
    status = request.get("status") if isinstance(request, dict) else None
    logger.progress("Health status: %s", status)
    if status != "OK":
        reason = request.get("reason") if isinstance(request, dict) else None
        raise ActionFailure(
            f"Arcanna health status is {status}: {reason or 'no reason given'}"
        )
    try:
        jobs = rows(client.get(consts.ENDPOINT_JOBS))
    except ActionFailure as exc:
        raise ActionFailure(
            f"The API key is valid but cannot list jobs: {exc}"
        ) from exc
    logger.progress("%s job(s) visible to this API key", len(jobs))
    soar.set_message(consts.MSG_TEST_OK)


def get_api_scopes(params: Params, soar: SOARClient, asset: Asset) -> list[ScopeOutput]:
    scopes = rows(ArcannaClient(asset).get(consts.ENDPOINT_TOKEN_SCOPES))
    soar.set_summary(TotalScopesSummary(total_scopes=len(scopes)))
    soar.set_message(f"{len(scopes)} scope(s)")
    return [ScopeOutput(scope=str(scope)) for scope in scopes]


def get_platform_metrics(
    params: Params, soar: SOARClient, asset: Asset
) -> PlatformMetricsOutput:
    payload = ArcannaClient(asset).post(consts.ENDPOINT_METRICS_PLATFORM, body={})
    soar.set_message("Platform metrics retrieved")
    return (
        PlatformMetricsOutput(**payload)
        if isinstance(payload, dict)
        else PlatformMetricsOutput(metrics=payload)
    )
