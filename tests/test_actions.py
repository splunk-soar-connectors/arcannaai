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

import json
from typing import Any

import httpx
import pytest
from soar_sdk.exceptions import ActionFailure
from soar_sdk.params import Params

from src.actions import events, feedback, jobs, platform
from src.app import app
from src.asset import Asset
from src.client import ArcannaClient


class FakeSoar:
    def __init__(self) -> None:
        self.summary: Any = None
        self.message = ""

    def set_summary(self, summary: object) -> None:
        self.summary = summary

    def set_message(self, message: str) -> None:
        self.message = message


class Arcanna:
    """Routes (method, path) to canned responses and records every request."""

    def __init__(self, routes: dict) -> None:
        self.routes = routes
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answer = self.routes[(request.method, request.url.path)]
        if isinstance(answer, list):
            answer = answer.pop(0) if len(answer) > 1 else answer[0]
        status, body = answer
        return httpx.Response(status, json=body)


@pytest.fixture
def arcanna(monkeypatch: pytest.MonkeyPatch):
    def install(routes: dict) -> Arcanna:
        server = Arcanna(routes)
        monkeypatch.setattr(ArcannaClient, "transport", httpx.MockTransport(server))
        return server

    return install


@pytest.fixture
def asset() -> Asset:
    return Asset(
        base_url="https://arcanna.test/",
        api_key="key",  # pragma: allowlist secret
        default_job_id=7,
        default_storage_name="soar-input",
    )


def test_connectivity_passes_when_health_is_ok(arcanna, asset):
    # given
    arcanna(
        {
            ("GET", "/api/v2/health/"): (200, {"request": {"status": "OK"}}),
            ("GET", "/api/v1/jobs/"): (200, [{"job_id": 7}]),
        }
    )
    soar = FakeSoar()
    # when
    platform.run_test_connectivity(soar, asset)
    # then
    assert soar.message == "Test connectivity passed"


def test_connectivity_fails_when_health_is_not_ok(arcanna, asset):
    # given
    arcanna(
        {
            ("GET", "/api/v2/health/"): (
                200,
                {"request": {"status": "NOK", "reason": "license"}},
            )
        }
    )
    # when / then
    with pytest.raises(ActionFailure, match="health status is NOK: license"):
        platform.run_test_connectivity(FakeSoar(), asset)


def test_http_error_carries_status_and_detail(arcanna, asset):
    # given
    arcanna({("GET", "/api/v1/jobs/7"): (401, {"detail": "Invalid API key"})})
    # when / then
    with pytest.raises(
        ActionFailure, match=r'Arcanna returned HTTP 401: "Invalid API key"'
    ):
        jobs.get_job(jobs.JobParams(), FakeSoar(), asset)


def test_api_key_header_is_sent(arcanna, asset):
    # given
    server = arcanna({("GET", "/api/v1/jobs/"): (200, [{"job_id": 7, "title": "SOC"}])})
    soar = FakeSoar()
    # when
    rows = jobs.list_jobs(Params(), soar, asset)
    # then
    assert server.requests[0].headers["x-arcanna-api-key"] == "key"
    assert [row.job_id for row in rows] == [7]
    assert soar.summary.total_jobs == 1


def test_job_id_must_be_an_integer(asset):
    # when / then
    with pytest.raises(ActionFailure, match="is not an integer"):
        jobs.get_job(jobs.JobParams(job_id=1.5), FakeSoar(), asset)


def test_job_id_is_required_without_default():
    # given
    bare = Asset(base_url="https://arcanna.test", api_key="key")
    # when / then
    with pytest.raises(ActionFailure, match="No job id given"):
        jobs.get_job(jobs.JobParams(), FakeSoar(), bare)


def test_send_event_reads_datapath_object_and_default_storage(arcanna, asset):
    # given
    server = arcanna(
        {
            ("POST", "/api/v1/events/"): (
                201,
                {"event_id": "e1", "status": "pending_inference", "storage_tag": "st1"},
            )
        }
    )
    soar = FakeSoar()
    params = events.SendEventParams(title="alert", event_json="{'src': '10.0.0.1'}")
    # when
    out = events.send_event(params, soar, asset)
    # then
    body = json.loads(server.requests[0].content)
    assert body == {
        "job_id": 7,
        "title": "alert",
        "raw_body": {"src": "10.0.0.1"},
        "storage_name": "soar-input",
    }
    assert (out.event_id, out.job_id, out.storage_tag) == ("e1", 7, "st1")
    assert soar.summary.storage_tag == "st1"


def test_send_event_refuses_several_artifacts(asset):
    # given
    params = events.SendEventParams(title="alert", event_json='[{"a": 1}, {"a": 2}]')
    # when / then
    with pytest.raises(ActionFailure, match="matched 2 objects"):
        events.send_event(params, FakeSoar(), asset)


def test_get_event_polls_until_the_event_is_stored_and_decided(
    arcanna, asset, monkeypatch
):
    # given
    monkeypatch.setattr(events.time, "sleep", lambda _: None)
    server = arcanna(
        {
            ("GET", "/api/v1/events/7/e1"): [
                (200, {"status": "ERROR", "error_message": "not found"}),
                (200, {"status": "pending_inference", "result": "no_decision"}),
                (
                    200,
                    {
                        "status": "OK",
                        "result": "escalate",
                        "result_label": "Escalate",
                        "confidence_score": 91.5,
                    },
                ),
            ]
        }
    )
    soar = FakeSoar()
    # when
    out = events.get_event(
        events.GetEventParams(event_id="e1", max_wait=60, poll_interval=1), soar, asset
    )
    # then
    assert len(server.requests) == 3
    assert server.requests[0].url.params["storage_name"] == "soar-input"
    assert (out.final, out.result_label, out.event_id) == (True, "Escalate", "e1")
    assert soar.summary.polls == 3
    assert soar.message.startswith("Decision for event e1: Escalate")


def test_get_event_fails_when_event_stays_unknown(arcanna, asset):
    # given
    arcanna(
        {
            ("GET", "/api/v1/events/7/e1"): (
                200,
                {"status": "ERROR", "error_message": "unknown event"},
            )
        }
    )
    # when / then
    with pytest.raises(ActionFailure, match="Event e1 not found in job 7 after 0 s"):
        events.get_event(events.GetEventParams(event_id="e1"), FakeSoar(), asset)


def test_get_event_limits_max_wait(asset):
    # when / then
    with pytest.raises(ActionFailure, match="between 0 and 300"):
        events.get_event(
            events.GetEventParams(event_id="e1", max_wait=301), FakeSoar(), asset
        )


def test_send_feedback_rejects_unknown_label(arcanna, asset):
    # given
    arcanna({("GET", "/api/v1/jobs/7/labels"): (200, ["Escalate", "Drop"])})
    params = feedback.SendFeedbackParams(event_id="e1", label="Resolved")
    # when / then
    with pytest.raises(ActionFailure, match="Label 'Resolved' is not a label of job 7"):
        feedback.send_feedback(params, FakeSoar(), asset)


def test_send_feedback_sends_label_user_and_storage(arcanna, asset):
    # given
    server = arcanna(
        {
            ("GET", "/api/v1/jobs/7/labels"): (200, ["Escalate", "Drop"]),
            ("PUT", "/api/v1/events/7/e1/feedback"): (200, {"status": "updated"}),
        }
    )
    soar = FakeSoar()
    params = feedback.SendFeedbackParams(
        event_id="e1", label="Drop", username="analyst", storage_name="st1"
    )
    # when
    out = feedback.send_feedback(params, soar, asset)
    # then
    put = server.requests[1]
    assert json.loads(put.content) == {"feedback": "Drop", "cortex_user": "analyst"}
    assert put.url.params["storage_name"] == "st1"
    assert out.status == "updated"
    assert soar.summary.arcanna_label == "Drop"


def test_query_events_builds_body_and_flattens_rows(arcanna, asset):
    # given
    server = arcanna(
        {
            ("POST", "/api/v2/events/query"): (
                200,
                {
                    "total_count": 3,
                    "events": [
                        {
                            "event_id": "e1",
                            "@timestamp": "t1",
                            "arcanna": {"result_label": "Drop", "confidence_score": 80},
                        }
                    ],
                },
            )
        }
    )
    soar = FakeSoar()
    params = events.QueryEventsParams(
        job_ids="1, 2",
        filters='{"field": "arcanna.result_label", "operator": "is", "value": "Drop"}',
        size=1,
    )
    # when
    rows = events.query_events(params, soar, asset)
    # then
    body = json.loads(server.requests[0].content)
    assert body["job_ids"] == [1, 2]
    assert body["filters"] == [
        {"field": "arcanna.result_label", "operator": "is", "value": "Drop"}
    ]
    assert (body["size"], body["page"], body["decision_points_only"]) == (1, 0, False)
    assert (rows[0].result_label, rows[0].timestamp) == ("Drop", "t1")
    assert (soar.summary.total_count, soar.summary.has_more) == (3, True)


def test_query_events_rejects_filter_without_operator(asset):
    # given
    params = events.QueryEventsParams(filters='[{"field": "x"}]')
    # when / then
    with pytest.raises(ActionFailure, match='needs "field" and "operator"'):
        events.query_events(params, FakeSoar(), asset)


def test_outliers_are_read_from_the_outliers_key(arcanna, asset):
    # given
    arcanna(
        {
            ("GET", "/api/v2/events/7/outliers"): (
                200,
                {"outliers": [{"event_id": "e9", "bucket_id": "b1"}]},
            )
        }
    )
    soar = FakeSoar()
    # when
    rows = jobs.get_outliers(jobs.JobParams(), soar, asset)
    # then
    assert [row.event_id for row in rows] == ["e9"]
    assert soar.summary.total_outliers == 1


def test_all_actions_are_registered():
    # when
    names = set(app.actions_manager.get_actions())
    # then
    assert len(names) == 19
    assert {
        "send_event",
        "get_event",
        "send_feedback",
        "query_events",
        "test_connectivity",
    } <= names
