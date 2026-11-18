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
from soar_sdk.params import Param, Params

from .. import consts
from ..asset import Asset
from ..client import ArcannaClient, resolve_job_id, storage_query


class SendFeedbackParams(Params):
    job_id: float | None = Param(
        description=consts.JOB_ID_DESCRIPTION,
        primary=True,
        cef_types=["arcanna job id"],
    )
    event_id: str = Param(
        description="Arcanna event id", primary=True, cef_types=["arcanna event id"]
    )
    label: str = Param(
        description="One of the job's labels, identical to the SOAR closing status"
    )
    username: str | None = Param(
        description="SOAR user who closed the case (for example the container owner); empty attributes the feedback to the API key's user"
    )
    storage_name: str | None = Param(
        description=consts.STORAGE_DESCRIPTION, cef_types=["arcanna storage tag"]
    )


class SendFeedbackOutput(PermissiveActionOutput):
    status: str | None = OutputField(column_name="Status")


class SendFeedbackSummary(ActionOutput):
    arcanna_label: str
    username: str | None = OutputField(cef_types=["user name"])


def send_feedback(
    params: SendFeedbackParams, soar: SOARClient, asset: Asset
) -> SendFeedbackOutput:
    job_id = resolve_job_id(params.job_id, asset)
    client = ArcannaClient(asset)
    # SOAR closing statuses must exist verbatim as labels of the job: no translation
    label = str(params.label).strip()
    labels = client.job_labels(job_id)
    if label not in labels:
        raise ActionFailure(
            consts.MSG_BAD_LABEL.format(
                label=label, job_id=job_id, labels=", ".join(labels) or "none"
            )
        )
    body = {"feedback": label}
    # without a username Arcanna attributes the feedback to the API key's user
    username = str(params.username or "").strip() or None
    if username:
        body["cortex_user"] = username
    payload = client.put(
        consts.ENDPOINT_FEEDBACK.format(job_id=job_id, event_id=params.event_id),
        params=storage_query(params.storage_name, asset),
        body=body,
    )
    soar.set_summary(SendFeedbackSummary(arcanna_label=label, username=username))
    soar.set_message(f"Feedback '{label}' sent for event {params.event_id}")
    return (
        SendFeedbackOutput(**payload)
        if isinstance(payload, dict)
        else SendFeedbackOutput(response=payload)
    )
