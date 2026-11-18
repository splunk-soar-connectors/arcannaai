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
from soar_sdk.params import Param, Params

from .. import consts
from ..asset import Asset
from ..client import ArcannaClient, resolve_job_id, rows


class JobParams(Params):
    job_id: float | None = Param(
        description=consts.JOB_ID_DESCRIPTION,
        primary=True,
        cef_types=["arcanna job id"],
    )


class JobByNameParams(Params):
    job_name: str = Param(description="Exact job title", primary=True)


class JobOutput(PermissiveActionOutput):
    job_id: int | None = OutputField(cef_types=["arcanna job id"], column_name="Job ID")
    title: str | None = OutputField(column_name="Title")
    category: str | None = OutputField(column_name="Category")
    status: str | None = OutputField(column_name="Status")


class LabelOutput(ActionOutput):
    label: str = OutputField(column_name="Label")


class OutlierOutput(PermissiveActionOutput):
    event_id: str | None = OutputField(
        cef_types=["arcanna event id"], column_name="Event ID"
    )
    event_url: str | None = OutputField(cef_types=["url"], column_name="Event URL")
    bucket_id: str | None = OutputField(column_name="Bucket ID")
    bucket_url: str | None = OutputField(cef_types=["url"])


class JobMetricsOutput(PermissiveActionOutput):
    total_events: float | None = None
    total_events_in_knowledge_base: float | None = None
    total_events_with_consensus: float | None = None
    time_saved_minutes: float | None = None
    active_model_id: str | None = None
    start_time: str | None = None
    end_time: str | None = None


class JobCommandOutput(PermissiveActionOutput):
    status: str | None = OutputField(column_name="Status")


class TotalJobsSummary(ActionOutput):
    total_jobs: int


class JobSummary(ActionOutput):
    job_id: int | None = OutputField(cef_types=["arcanna job id"])


class TotalLabelsSummary(ActionOutput):
    total_labels: int


class TotalOutliersSummary(ActionOutput):
    total_outliers: int


class JobMetricsSummary(ActionOutput):
    job_id: int = OutputField(cef_types=["arcanna job id"])
    total_events: float | None = None


class JobCommandSummary(ActionOutput):
    job_id: int = OutputField(cef_types=["arcanna job id"])
    command: str


def list_jobs(params: Params, soar: SOARClient, asset: Asset) -> list[JobOutput]:
    jobs = rows(ArcannaClient(asset).get(consts.ENDPOINT_JOBS))
    soar.set_summary(TotalJobsSummary(total_jobs=len(jobs)))
    soar.set_message(f"{len(jobs)} job(s)")
    return [JobOutput(**job) for job in jobs if isinstance(job, dict)]


def get_job(params: JobParams, soar: SOARClient, asset: Asset) -> JobOutput:
    job_id = resolve_job_id(params.job_id, asset)
    payload = ArcannaClient(asset).get(consts.ENDPOINT_JOB.format(job_id=job_id))
    soar.set_summary(JobSummary(job_id=job_id))
    soar.set_message(f"Job {job_id} retrieved")
    return (
        JobOutput(**payload)
        if isinstance(payload, dict)
        else JobOutput(response=payload)
    )


def get_job_by_name(
    params: JobByNameParams, soar: SOARClient, asset: Asset
) -> JobOutput:
    # exact title match, done by the server (HTTP 400 'Invalid Job Name' when no job has that title)
    payload = ArcannaClient(asset).post(
        consts.ENDPOINT_JOB_BY_NAME, body={"job_name": params.job_name}
    )
    payload = payload if isinstance(payload, dict) else {"response": payload}
    soar.set_summary(JobSummary(job_id=payload.get("job_id")))
    soar.set_message(f"Job '{params.job_name}' retrieved")
    return JobOutput(**payload)


def list_labels(params: JobParams, soar: SOARClient, asset: Asset) -> list[LabelOutput]:
    job_id = resolve_job_id(params.job_id, asset)
    labels = ArcannaClient(asset).job_labels(job_id)
    soar.set_summary(TotalLabelsSummary(total_labels=len(labels)))
    soar.set_message(f"{len(labels)} label(s)")
    return [LabelOutput(label=label) for label in labels]


def _job_command(
    params: JobParams, soar: SOARClient, asset: Asset, verb: str, endpoint: str
) -> JobCommandOutput:
    job_id = resolve_job_id(params.job_id, asset)
    payload = ArcannaClient(asset).post(endpoint.format(job_id=job_id))
    soar.set_summary(JobCommandSummary(job_id=job_id, command=verb))
    soar.set_message(f"Job {job_id} {verb} requested")
    return (
        JobCommandOutput(**payload)
        if isinstance(payload, dict)
        else JobCommandOutput(response=payload)
    )


def start_job(params: JobParams, soar: SOARClient, asset: Asset) -> JobCommandOutput:
    return _job_command(params, soar, asset, "start", consts.ENDPOINT_JOB_START)


def stop_job(params: JobParams, soar: SOARClient, asset: Asset) -> JobCommandOutput:
    return _job_command(params, soar, asset, "stop", consts.ENDPOINT_JOB_STOP)


def train_job(params: JobParams, soar: SOARClient, asset: Asset) -> JobCommandOutput:
    return _job_command(params, soar, asset, "train", consts.ENDPOINT_JOB_TRAIN)


def get_outliers(
    params: JobParams, soar: SOARClient, asset: Asset
) -> list[OutlierOutput]:
    job_id = resolve_job_id(params.job_id, asset)
    outliers = rows(
        ArcannaClient(asset).get(consts.ENDPOINT_JOB_OUTLIERS.format(job_id=job_id)),
        "outliers",
    )
    soar.set_summary(TotalOutliersSummary(total_outliers=len(outliers)))
    soar.set_message(f"{len(outliers)} outlier(s)")
    return [OutlierOutput(**row) for row in outliers if isinstance(row, dict)]


def get_job_metrics(
    params: JobParams, soar: SOARClient, asset: Asset
) -> JobMetricsOutput:
    job_id = resolve_job_id(params.job_id, asset)
    payload = ArcannaClient(asset).post(
        consts.ENDPOINT_METRICS_JOB, params={"job_id": job_id}
    )
    payload = payload if isinstance(payload, dict) else {"response": payload}
    soar.set_summary(
        JobMetricsSummary(job_id=job_id, total_events=payload.get("total_events"))
    )
    soar.set_message(f"Metrics of job {job_id} retrieved")
    return JobMetricsOutput(**payload)
