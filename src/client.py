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

import ast
import json
from typing import Any

import httpx
from soar_sdk.exceptions import ActionFailure
from soar_sdk.logging import getLogger

from . import consts
from .asset import Asset

logger = getLogger()


def to_int(value: Any) -> int:
    """SOAR hands numeric parameters over as int, float or text ('120', '120.0')."""
    if isinstance(value, bool):
        raise ValueError(value)
    number = float(value)
    if not number.is_integer():
        raise ValueError(value)
    return int(number)


def int_param(value: Any, name: str, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        return to_int(value)
    except (TypeError, ValueError) as exc:
        raise ActionFailure(consts.MSG_BAD_INT.format(name=name, value=value)) from exc


def resolve_job_id(value: Any, asset: Asset) -> int:
    """The job id of the action, else the asset's default job id."""
    if value in (None, ""):
        value = asset.default_job_id
    if value in (None, "", -1, "-1"):
        raise ActionFailure(consts.MSG_NO_JOB)
    try:
        return to_int(value)
    except (TypeError, ValueError) as exc:
        raise ActionFailure(consts.MSG_BAD_JOB.format(value=value)) from exc


def resolve_storage(value: str | None, asset: Asset) -> str | None:
    """Storage of the job's REST input (display name or storage tag); None lets
    Arcanna pick the only storage tied to the API key."""
    storage = str(value or asset.default_storage_name or "").strip()
    return storage or None


def storage_query(value: str | None, asset: Asset) -> dict | None:
    storage = resolve_storage(value, asset)
    return {"storage_name": storage} if storage else None


def load_json(name: str, text: Any, expect: tuple[type, ...] = (dict, list)) -> Any:
    """A JSON string typed by hand, or the object a playbook datapath hands over
    directly (for example artifact:*.cef)."""
    value = text
    if isinstance(value, bytes | bytearray):
        value = value.decode("utf-8", "replace")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError as exc:
            # the playbook engine renders a datapath object with Python quoting; read it as a literal, never eval
            try:
                value = ast.literal_eval(value)
            except (ValueError, SyntaxError, MemoryError, RecursionError):
                raise ActionFailure(
                    consts.MSG_INVALID_JSON.format(name=name, error=exc)
                ) from exc
    if (
        expect == (dict,)
        and isinstance(value, list)
        and len(value) == 1
        and isinstance(value[0], dict)
    ):
        value = value[0]
    if expect == (dict,) and isinstance(value, list):
        raise ActionFailure(
            f"The value of '{name}' matched {len(value)} objects; this action sends ONE event per run - narrow the datapath with a filter block"
        )
    if not isinstance(value, expect):
        raise ActionFailure(
            "The value of '{}' must be a JSON {}".format(
                name, " or ".join(t.__name__ for t in expect)
            )
        )
    return value


def rows(payload: Any, key: str | None = None) -> list:
    """Rows of a list response, or of the list under `key` of an object response."""
    if key is not None:
        payload = payload.get(key) if isinstance(payload, dict) else None
    return payload if isinstance(payload, list) else []


class ArcannaClient:
    # tests replace the transport; None uses the network
    transport: httpx.BaseTransport | None = None

    def __init__(self, asset: Asset) -> None:
        self.timeout = asset.timeout or consts.DEFAULT_TIMEOUT
        verify = True if asset.verify_server_cert is None else asset.verify_server_cert
        self._client = httpx.Client(
            base_url=asset.base_url.rstrip("/"),
            headers={
                "accept": "application/json",
                consts.ARCANNA_API_KEY_HEADER: asset.api_key,
            },
            verify=verify,
            timeout=self.timeout,
            transport=self.transport,
        )

    def request(
        self, method: str, endpoint: str, params: dict | None = None, body: Any = None
    ) -> Any:
        try:
            response = self._client.request(
                method.upper(), endpoint, params=params, json=body
            )
        except httpx.TimeoutException as exc:
            raise ActionFailure(
                f"Arcanna did not answer within {self.timeout} seconds"
            ) from exc
        except httpx.ConnectError as exc:
            raise ActionFailure(f"Unable to connect to Arcanna: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ActionFailure(f"Error connecting to Arcanna: {exc}") from exc
        return self._payload(response)

    @staticmethod
    def _payload(response: httpx.Response) -> Any:
        logger.debug("Arcanna answered HTTP %s", response.status_code)
        text = response.text or ""
        if "json" in response.headers.get(
            "Content-Type", ""
        ) or text.strip().startswith(("{", "[")):
            try:
                payload = response.json()
            except ValueError as exc:
                raise ActionFailure(
                    f"Unable to parse the JSON response: {exc}"
                ) from exc
        else:
            payload = {"text": text[:2000]}
        if response.is_success:
            return payload
        detail = payload.get("detail") if isinstance(payload, dict) else None
        raise ActionFailure(
            f"Arcanna returned HTTP {response.status_code}: {json.dumps(detail or payload)[:500]}"
        )

    def get(self, endpoint: str, params: dict | None = None) -> Any:
        return self.request("get", endpoint, params=params)

    def post(self, endpoint: str, params: dict | None = None, body: Any = None) -> Any:
        return self.request("post", endpoint, params=params, body=body)

    def put(self, endpoint: str, params: dict | None = None, body: Any = None) -> Any:
        return self.request("put", endpoint, params=params, body=body)

    def job_labels(self, job_id: int) -> list[str]:
        return [
            str(label)
            for label in rows(
                self.get(consts.ENDPOINT_JOB_LABELS.format(job_id=job_id))
            )
        ]
