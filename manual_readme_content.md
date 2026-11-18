# Arcanna.ai app for Splunk SOAR

Connects Splunk SOAR to an Arcanna.ai instance so that playbooks can send
alerts to an Arcanna job, read the AI decision back, and return the
analyst's verdict as feedback. Built against the Arcanna.ai 1.93.0 REST API
(v1 event, feedback and job routes; v2 query, metrics, outlier and
reprocess routes).

## Asset configuration

| Setting | Required | Meaning |
|---|---|---|
| Base URL | yes | Arcanna API base URL, for example `https://arcanna.example.com` |
| API key | yes | Sent as the `x-arcanna-api-key` header. Use a key with the scopes the actions need (`get api scopes` shows them). |
| Verify server certificate | no | Default on |
| Default job id | no | Used when an action is run without a job id (not by `query events`) |
| Default storage name | no | Storage of the job's REST input used when an action is run without one; see "Storages" |
| Timeout | no | HTTP timeout in seconds, default 60 |

## Storages

Each REST input of an Arcanna job writes to its own storage (storage tag).
`send event`, `get event`, `export event`, `get reasoning` and
`send feedback` act on one storage, chosen by `storage_name` (the storage's
display name or its storage tag), else the asset's default storage name,
else by Arcanna:

- the API key reaches exactly one storage of the job: that one is used;
- it reaches several (several REST inputs share the key, or the key is
  global): HTTP 400 "There are multiple storages associated with this api
  key", so a storage name is required;
- it reaches none: HTTP 404.

`send event` returns the `storage_tag` the event was stored in; pass it as
`storage_name` to the later actions on that event. `get outliers` and
`reprocess event` use every storage the key reaches, and `query events`
without job ids searches every job and storage the key may read.

## Job labels must mirror the SOAR closing statuses

The app does not translate verdicts. `send feedback` sends the label exactly
as given and accepts it only when it is one of the job's labels
(`list labels`); any other value fails the action with the list of valid
labels. Create the Arcanna job's labels with the same names as the SOAR
closing statuses you feed back: if SOAR closes a case as `Benign`, the job
must have a label `Benign` (same spelling and case).

## Actions

| Action | Type | Route | Notes |
|---|---|---|---|
| test connectivity | test | `GET /api/v2/health/`, `GET /api/v1/jobs/` | the key must get `{"request": {"status": "OK"}}` from health (needs the health-check scope), then the jobs it sees are listed |
| list jobs | investigate | `GET /api/v1/jobs/` | job id, title, category, status |
| get job | investigate | `GET /api/v1/jobs/{job_id}` | one job by id |
| get job by name | investigate | `POST /api/v1/jobs/get_by_name` | body `{"job_name": ...}`; exact title match by the server, HTTP 400 `Invalid Job Name` when no job has that title |
| list labels | investigate | `GET /api/v1/jobs/{job_id}/labels` | the label names of the job; the only values `send feedback` accepts |
| get outliers | investigate | `GET /api/v2/events/{job_id}/outliers` | event id and URL, bucket id and URL of each outlier |
| get job metrics | investigate | `POST /api/v2/metrics/job?job_id=` | job id as query parameter |
| query events | investigate | `POST /api/v2/events/query` | job ids (optional list of integers; none = every job and storage the key may read), event ids, size, page, date range, filters, decision points only; returns events with decisions, the total count and whether more pages exist |
| get platform metrics | investigate | `POST /api/v2/metrics/platform_metrics` | platform and storage-cluster overview |
| start job / stop job / train job | generic | `POST /api/v1/jobs/{job_id}/start|stop|train` | training changes the model that scores production events |
| send event | generic | `POST /api/v1/events/` | body `{job_id, title, raw_body, storage_name}`; returns the event id and storage tag |
| get event | investigate | `GET /api/v1/events/{job_id}/{event_id}` | decision label and value, confidence, bucket state, outlier; finished when the result is set and is not `no_decision` ("No decision" is the label while inference is pending); an event not stored yet (ingestion is asynchronous) is read again; fails when it is still unknown when `max_wait` expires; `max_wait` is 0-300 s, 0 reads once; needs the license feature for event investigation (HTTP 401 "Feature not available in this license plan" otherwise) |
| export event | investigate | `GET /api/v1/events/{job_id}/{event_id}/export` | the stored event with its decision data |
| get reasoning | investigate | `GET /api/v1/events/{job_id}/{event_id}/get_summarization_reasoning` | reasoning and summarization text with their processing status |
| send feedback | generic | `PUT /api/v1/events/{job_id}/{event_id}/feedback` | body `{"cortex_user": <username>, "feedback": <label>}`; `cortex_user` is the SOAR user given as `username` (for example `container:owner_name`); when empty it is not sent and Arcanna attributes the feedback to the API key's user (HTTP 404 "API key user not found in Arcanna" if that user no longer exists); the label must be one of the job's labels |
| reprocess event | generic | `POST /api/v2/events/{job_id}/{event_id}/reprocess` | asks Arcanna to decide the event again |
| get api scopes | investigate | `GET /api/v2/token/scopes` | scopes of the configured key |

Every action puts the HTTP status and the response text in the action
result's debug data. Errors are returned as the action message; nothing is
retried silently.

## Query events: filters and paging

`filters` is a JSON array of `{"field", "operator", "value"}` objects (one
object alone is accepted too). Fields are event fields of the job's results,
`arcanna.*` for the decision fields. Operators: `is`, `is not`, `is one of`,
`is not one of`, `contains`, `not contains`, `starts with`,
`not starts with`, `exists`, `doesn't exist`, `less than`,
`less than or equal to`, `greater than`, `greater than or equal to`.

Events the job decided as `Benign` in the last 7 days with a confidence of at
least 80 (the score is 0-100), 100 per page:

| Parameter | Value |
|---|---|
| job_ids | `12, 14` (or empty for every job the key may read) |
| start_date | `now-7d` |
| end_date | `now` |
| size | `100` |
| page | `0` |
| filters | `[{"field": "arcanna.result_label", "operator": "is", "value": "Benign"}, {"field": "arcanna.confidence_score", "operator": "greater than or equal to", "value": 80}]` |

Results are newest first. The summary carries `total_count`, `page` and
`has_more`; while `has_more` is true, run the action again with `page` + 1.

## Typical playbook

1. `send event` with the alert fields as `event_json` (the datapath
   `artifact:*.cef` of the alert's artifact, narrowed with a filter block when
   the container holds several artifacts), the alert name as `title`
   (`container:name`).
1. `get event` with `max_wait` (for example 120, at most 300) to wait for the decision,
   and `storage_name` = the `storage_tag` returned by `send event` when the
   job has several storages;
   use `result_label`, `confidence_score`, `bucket_state` and `outlier` to
   route the case.
1. On closure, `send feedback` with the SOAR closing status as `label` and
   the analyst's name so the model keeps learning. The closing status must
   exist as a label of the job (see "Job labels must mirror the SOAR closing
   statuses").

## Verification status of this build

Every route, request body and response field used by the actions was
checked against the Arcanna.ai 1.93.0 exposer API source, and the app was
tested on a live Splunk SOAR instance connected to Arcanna.ai 1.93.0.

## Requirements

Splunk SOAR 7.0 or later (Python 3.13). The app is built on the Splunk SOAR SDK and needs no other dependencies.
