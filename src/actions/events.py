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

import time

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput, OutputField, PermissiveActionOutput
from soar_sdk.exceptions import ActionFailure
from soar_sdk.logging import getLogger
from soar_sdk.params import Param, Params

from .. import consts
from ..asset import Asset
from ..client import (
    ArcannaClient,
    int_param,
    load_json,
    resolve_job_id,
    resolve_storage,
    storage_query,
    to_int,
)

logger = getLogger()


class SendEventParams(Params):
    job_id: float | None = Param(
        description=consts.JOB_ID_DESCRIPTION,
        primary=True,
        cef_types=["arcanna job id"],
    )
    title: str = Param(description="Event title (for example the alert name)")
    event_json: str = Param(
        description="The event as a JSON object: a JSON string, or a playbook datapath to the fields (for example artifact:*.cef)"
    )
    storage_name: str | None = Param(
        description=consts.STORAGE_DESCRIPTION, cef_types=["arcanna storage tag"]
    )


class GetEventParams(Params):
    job_id: float | None = Param(
        description=consts.JOB_ID_DESCRIPTION,
        primary=True,
        cef_types=["arcanna job id"],
    )
    event_id: str = Param(
        description="Arcanna event id returned by 'send event'",
        primary=True,
        cef_types=["arcanna event id"],
    )
    max_wait: float | None = Param(
        description="Seconds to wait for a final decision, 0 to 300 (0 = read once)",
        default=0,
    )
    poll_interval: float | None = Param(
        description="Seconds between polls while waiting", default=5
    )
    storage_name: str | None = Param(
        description=consts.STORAGE_DESCRIPTION, cef_types=["arcanna storage tag"]
    )


class EventParams(Params):
    job_id: float | None = Param(
        description=consts.JOB_ID_DESCRIPTION,
        primary=True,
        cef_types=["arcanna job id"],
    )
    event_id: str = Param(
        description="Arcanna event id", primary=True, cef_types=["arcanna event id"]
    )
    storage_name: str | None = Param(
        description=consts.STORAGE_DESCRIPTION, cef_types=["arcanna storage tag"]
    )


class ReprocessEventParams(Params):
    job_id: float | None = Param(
        description=consts.JOB_ID_DESCRIPTION,
        primary=True,
        cef_types=["arcanna job id"],
    )
    event_id: str = Param(
        description="Arcanna event id", primary=True, cef_types=["arcanna event id"]
    )


class QueryEventsParams(Params):
    job_ids: str | None = Param(
        description="Arcanna job ids (a list, or comma separated text); empty searches every job (and every storage) the API key can read",
        primary=True,
        cef_types=["arcanna job id"],
        allow_list=True,
    )
    event_ids: str | None = Param(
        description="Comma separated Arcanna event ids", cef_types=["arcanna event id"]
    )
    size: float | None = Param(
        description="Maximum number of events (default 50)", default=50
    )
    start_date: str | None = Param(
        description="Start of the time range (ISO 8601 or Elasticsearch date math such as now-7d)"
    )
    end_date: str | None = Param(
        description="End of the time range (ISO 8601 or date math such as now)"
    )
    filters: str | None = Param(
        description=(
            'JSON array of filter objects {"field", "operator", "value"}; a single object is accepted. Operators: is, is not, '
            "is one of, is not one of, contains, not contains, starts with, not starts with, exists, doesn't exist, less than, "
            "less than or equal to, greater than, greater than or equal to"
        )
    )
    page: float | None = Param(
        description="Result page, counting from 0 (page * size events are skipped)",
        default=0,
    )
    decision_points_only: bool | None = Param(
        description="Return only event ids and decision points, without the Arcanna decision fields and the raw event",
        default=False,
    )


class SendEventOutput(PermissiveActionOutput):
    event_id: str | None = OutputField(
        cef_types=["arcanna event id"], column_name="Event ID"
    )
    job_id: int | None = OutputField(cef_types=["arcanna job id"], column_name="Job ID")
    storage_tag: str | None = OutputField(cef_types=["arcanna storage tag"])
    status: str | None = OutputField(column_name="Status")
    ingest_timestamp: str | None = OutputField(column_name="Ingested")
    error_message: str | None = OutputField(column_name="Error")


class GetEventOutput(PermissiveActionOutput):
    event_id: str | None = OutputField(
        cef_types=["arcanna event id"], column_name="Event ID"
    )
    status: str | None = OutputField(column_name="Status")
    storage_tag: str | None = OutputField(cef_types=["arcanna storage tag"])
    result_label: str | None = OutputField(column_name="Decision")
    result: str | None = None
    confidence_score: float | None = OutputField(column_name="Confidence")
    bucket_state: str | None = OutputField(column_name="Bucket state")
    outlier: bool | None = OutputField(column_name="Outlier")
    ingest_timestamp: str | None = None
    error_message: str | None = None
    knowledge_base_state: str | None = None
    final: bool | None = OutputField(column_name="Final")


class ExportEventOutput(PermissiveActionOutput):
    event_id: str | None = OutputField(
        cef_types=["arcanna event id"], column_name="Event ID"
    )
    status: str | None = OutputField(column_name="Status")
    ingest_timestamp: str | None = OutputField(column_name="Ingested")
    storage_tag: str | None = OutputField(cef_types=["arcanna storage tag"])


class ReasoningPart(PermissiveActionOutput):
    text: str | None = None
    processing_status: str | None = None
    error: str | None = None


class GetReasoningOutput(PermissiveActionOutput):
    reasoning: ReasoningPart | None = None
    summarization: ReasoningPart | None = None


class ReprocessRequest(PermissiveActionOutput):
    status: str | None = OutputField(column_name="Status")


class ReprocessEventOutput(PermissiveActionOutput):
    request: ReprocessRequest | None = None


class QueryEventsOutput(PermissiveActionOutput):
    event_id: str | None = OutputField(
        cef_types=["arcanna event id"], column_name="Event ID"
    )
    job_id: int | None = OutputField(cef_types=["arcanna job id"])
    job_title: str | None = None
    result_label: str | None = OutputField(column_name="Decision")
    confidence_score: float | None = OutputField(column_name="Confidence")
    bucket_state: str | None = OutputField(column_name="Bucket state")
    timestamp: str | None = OutputField(column_name="Timestamp")


class SendEventSummary(ActionOutput):
    event_id: str | None = OutputField(cef_types=["arcanna event id"])
    job_id: int = OutputField(cef_types=["arcanna job id"])
    status: str | None = None
    storage_tag: str | None = OutputField(cef_types=["arcanna storage tag"])


class GetEventSummary(ActionOutput):
    event_id: str = OutputField(cef_types=["arcanna event id"])
    job_id: int = OutputField(cef_types=["arcanna job id"])
    final: bool
    result_label: str | None = None
    result: str | None = None
    confidence_score: float | None = None
    bucket_state: str | None = None
    outlier: bool | None = None
    status: str | None = None
    polls: int
    waited_seconds: int


class EventSummary(ActionOutput):
    event_id: str = OutputField(cef_types=["arcanna event id"])


class QueryEventsSummary(ActionOutput):
    returned: int
    total_count: int | None = None
    page: int
    has_more: bool


def send_event(
    params: SendEventParams, soar: SOARClient, asset: Asset
) -> SendEventOutput:
    job_id = resolve_job_id(params.job_id, asset)
    raw = load_json("event_json", params.event_json, (dict,))
    body = {"job_id": job_id, "title": params.title, "raw_body": raw}
    storage = resolve_storage(params.storage_name, asset)
    if storage:
        body["storage_name"] = storage
    payload = ArcannaClient(asset).post(consts.ENDPOINT_EVENTS, body=body)
    payload = payload if isinstance(payload, dict) else {"response": payload}
    payload.setdefault("job_id", job_id)
    soar.set_summary(
        SendEventSummary(
            event_id=payload.get("event_id"),
            job_id=job_id,
            status=payload.get("status"),
            storage_tag=payload.get("storage_tag"),
        )
    )
    soar.set_message("Event {} sent to job {}".format(payload.get("event_id"), job_id))
    return SendEventOutput(**payload)


def _is_found(event: dict) -> bool:
    # 200 with status ERROR while the event is not stored yet: ingestion is asynchronous
    return (
        str(event.get("status") or "").strip().upper() != consts.EVENT_NOT_FOUND_STATUS
    )


def _is_final(event: dict) -> bool:
    # finished when the machine result is set and is not 'no_decision' ('No decision' is the pending label)
    result = str(event.get("result") or "").strip().lower()
    return bool(result and result not in consts.NO_DECISION_VALUES)


def get_event(params: GetEventParams, soar: SOARClient, asset: Asset) -> GetEventOutput:
    job_id = resolve_job_id(params.job_id, asset)
    event_id = params.event_id
    max_wait = int_param(params.max_wait, "max_wait", 0)
    interval = int_param(params.poll_interval, "poll_interval", 5)
    if not 0 <= max_wait <= consts.MAX_WAIT_LIMIT:
        raise ActionFailure(
            f"max_wait must be between 0 and {consts.MAX_WAIT_LIMIT} seconds; use a playbook loop for longer waits"
        )
    interval = max(1, interval)
    client = ArcannaClient(asset)
    query = storage_query(params.storage_name, asset)
    started = time.monotonic()
    deadline = started + max_wait
    polls = 0
    while True:
        polls += 1
        payload = client.get(
            consts.ENDPOINT_EVENT.format(job_id=job_id, event_id=event_id), params=query
        )
        event = dict(payload) if isinstance(payload, dict) else {"response": payload}
        found = _is_found(event)
        final = found and _is_final(event)
        if final or time.monotonic() >= deadline:
            break
        logger.progress(
            "Decision pending (status %s), reading again in %s s",
            event.get("status") or "unknown",
            interval,
        )
        time.sleep(interval)
    waited = int(time.monotonic() - started)
    if not found:
        raise ActionFailure(
            "Event {} not found in job {} after {} s: {}".format(
                event_id, job_id, waited, event.get("error_message") or "unknown event"
            )
        )
    event.setdefault("event_id", event_id)
    event["final"] = final
    soar.set_summary(
        GetEventSummary(
            event_id=event_id,
            job_id=job_id,
            final=final,
            result_label=event.get("result_label") if final else None,
            result=event.get("result") if final else None,
            confidence_score=event.get("confidence_score"),
            bucket_state=event.get("bucket_state"),
            outlier=event.get("outlier"),
            status=event.get("status"),
            polls=polls,
            waited_seconds=waited,
        )
    )
    if final:
        soar.set_message(
            "Decision for event {}: {} ({}), confidence {}".format(
                event_id,
                event.get("result_label"),
                event.get("result"),
                event.get("confidence_score"),
            )
        )
    else:
        soar.set_message(
            "No decision yet for event {} (status {}) after {} s".format(
                event_id, event.get("status") or "unknown", waited
            )
        )
    return GetEventOutput(**event)


def export_event(
    params: EventParams, soar: SOARClient, asset: Asset
) -> ExportEventOutput:
    job_id = resolve_job_id(params.job_id, asset)
    payload = ArcannaClient(asset).get(
        consts.ENDPOINT_EVENT_EXPORT.format(job_id=job_id, event_id=params.event_id),
        params=storage_query(params.storage_name, asset),
    )
    soar.set_summary(EventSummary(event_id=params.event_id))
    soar.set_message(f"Event {params.event_id} exported")
    return (
        ExportEventOutput(**payload)
        if isinstance(payload, dict)
        else ExportEventOutput(response=payload)
    )


def get_reasoning(
    params: EventParams, soar: SOARClient, asset: Asset
) -> GetReasoningOutput:
    job_id = resolve_job_id(params.job_id, asset)
    payload = ArcannaClient(asset).get(
        consts.ENDPOINT_EVENT_REASONING.format(job_id=job_id, event_id=params.event_id),
        params=storage_query(params.storage_name, asset),
    )
    soar.set_summary(EventSummary(event_id=params.event_id))
    soar.set_message(f"Reasoning for event {params.event_id} retrieved")
    return (
        GetReasoningOutput(**payload)
        if isinstance(payload, dict)
        else GetReasoningOutput(response=payload)
    )


def reprocess_event(
    params: ReprocessEventParams, soar: SOARClient, asset: Asset
) -> ReprocessEventOutput:
    job_id = resolve_job_id(params.job_id, asset)
    payload = ArcannaClient(asset).post(
        consts.ENDPOINT_EVENT_REPROCESS.format(job_id=job_id, event_id=params.event_id)
    )
    soar.set_message(f"Reprocessing of event {params.event_id} requested")
    return (
        ReprocessEventOutput(**payload)
        if isinstance(payload, dict)
        else ReprocessEventOutput(response=payload)
    )


def _query_body(params: QueryEventsParams) -> dict:
    body: dict = {}
    # no job ids: Arcanna searches every job (and storage) the API key may read
    job_ids = params.job_ids
    if job_ids not in (None, ""):
        raw_ids = job_ids if isinstance(job_ids, list) else str(job_ids).split(",")
        try:
            body["job_ids"] = [to_int(x) for x in raw_ids if str(x).strip()]
        except (TypeError, ValueError) as exc:
            raise ActionFailure(
                f"job_ids must be a list of integers, got '{job_ids}'"
            ) from exc
    if params.event_ids:
        body["event_ids"] = [
            x.strip() for x in str(params.event_ids).split(",") if x.strip()
        ]
    if params.start_date:
        body["start_date"] = params.start_date
    if params.end_date:
        body["end_date"] = params.end_date
    body["decision_points_only"] = (
        str(params.decision_points_only).strip().lower() == "true"
    )
    body["size"] = int_param(params.size, "size", 50)
    body["page"] = int_param(params.page, "page", 0)
    if body["size"] < 1 or body["page"] < 0:
        raise ActionFailure("size must be at least 1 and page at least 0")
    if params.filters:
        filters = load_json("filters", params.filters)
        filters = [filters] if isinstance(filters, dict) else filters
        if not all(
            isinstance(f, dict) and f.get("field") and f.get("operator")
            for f in filters
        ):
            raise ActionFailure(
                'Each filter needs "field" and "operator", for example {"field": "arcanna.result_label", "operator": "is", "value": "Benign"}'
            )
        body["filters"] = filters
    return body


def _query_row(event: object) -> dict:
    if not isinstance(event, dict):
        return {"event": event}
    row = dict(event)
    nested = event.get("arcanna")
    if isinstance(nested, dict):
        for key in (
            "result_label",
            "result",
            "confidence_score",
            "bucket_state",
            "outlier",
            "status",
            "knowledge_base_state",
        ):
            if key in nested and key not in row:
                row[key] = nested[key]
    if "timestamp" not in row and "@timestamp" in row:
        row["timestamp"] = row["@timestamp"]
    return row


def query_events(
    params: QueryEventsParams, soar: SOARClient, asset: Asset
) -> list[QueryEventsOutput]:
    body = _query_body(params)
    payload = ArcannaClient(asset).post(consts.ENDPOINT_EVENTS_QUERY, body=body)
    events = payload.get("events") if isinstance(payload, dict) else payload
    events = events if isinstance(events, list) else []
    total = payload.get("total_count") if isinstance(payload, dict) else len(events)
    has_more = isinstance(total, int) and (body["page"] + 1) * body["size"] < total
    soar.set_summary(
        QueryEventsSummary(
            returned=len(events),
            total_count=total if isinstance(total, int) else None,
            page=body["page"],
            has_more=has_more,
        )
    )
    soar.set_message(
        "{} of {} event(s), page {}".format(len(events), total, body["page"])
    )
    return [QueryEventsOutput(**_query_row(event)) for event in events]
