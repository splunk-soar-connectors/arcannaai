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

ARCANNA_API_KEY_HEADER = (
    "x-arcanna-api-key"  # pragma: allowlist secret (a header name, not a key)
)

# routes served by Arcanna 1.93
ENDPOINT_HEALTH = "/api/v2/health/"
ENDPOINT_JOBS = "/api/v1/jobs/"
ENDPOINT_JOB = "/api/v1/jobs/{job_id}"
ENDPOINT_JOB_BY_NAME = "/api/v1/jobs/get_by_name"
ENDPOINT_JOB_LABELS = "/api/v1/jobs/{job_id}/labels"
ENDPOINT_JOB_START = "/api/v1/jobs/{job_id}/start"
ENDPOINT_JOB_STOP = "/api/v1/jobs/{job_id}/stop"
ENDPOINT_JOB_TRAIN = "/api/v1/jobs/{job_id}/train"
ENDPOINT_EVENTS = "/api/v1/events/"
ENDPOINT_EVENT = "/api/v1/events/{job_id}/{event_id}"
ENDPOINT_EVENT_EXPORT = "/api/v1/events/{job_id}/{event_id}/export"
ENDPOINT_EVENT_REASONING = (
    "/api/v1/events/{job_id}/{event_id}/get_summarization_reasoning"
)
ENDPOINT_FEEDBACK = "/api/v1/events/{job_id}/{event_id}/feedback"
ENDPOINT_EVENT_REPROCESS = "/api/v2/events/{job_id}/{event_id}/reprocess"
ENDPOINT_JOB_OUTLIERS = "/api/v2/events/{job_id}/outliers"
ENDPOINT_EVENTS_QUERY = "/api/v2/events/query"
ENDPOINT_TOKEN_SCOPES = "/api/v2/token/scopes"  # noqa: S105 (a route, not a password)
ENDPOINT_METRICS_JOB = "/api/v2/metrics/job"
ENDPOINT_METRICS_PLATFORM = "/api/v2/metrics/platform_metrics"

DEFAULT_TIMEOUT = 60

# an event is finished when its result is set and is not one of these
NO_DECISION_VALUES = ("no_decision",)
# status of GET /api/v1/events/{job_id}/{event_id} when the event is not (yet) stored
EVENT_NOT_FOUND_STATUS = "ERROR"

# get event blocks a SOAR action worker while it waits
MAX_WAIT_LIMIT = 300

MSG_TEST_START = "Connecting to the Arcanna.ai endpoint"
MSG_TEST_OK = "Test connectivity passed"
MSG_INVALID_JSON = "The value of '{name}' is not valid JSON: {error}"
MSG_NO_JOB = "No job id given and no default job id configured on the asset"
MSG_BAD_JOB = "Job id '{value}' is not an integer"
MSG_BAD_INT = "'{name}' must be an integer, got '{value}'"
MSG_BAD_LABEL = (
    "Label '{label}' is not a label of job {job_id}; the job labels are: {labels}"
)

STORAGE_DESCRIPTION = (
    "Storage name or storage tag of the event (defaults to the asset's default storage name; "
    "leave empty when the API key reaches one storage of the job)"
)
JOB_ID_DESCRIPTION = "Arcanna job id (defaults to the asset's default job id)"
