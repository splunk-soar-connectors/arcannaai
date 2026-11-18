# Arcanna.ai

Publisher: Arcanna Team <br>
Connector Version: 1.0.2 <br>
Product Vendor: Arcanna <br>
Product Name: Arcanna.ai <br>
Minimum Product Version: 7.0.0

Decision intelligence for security operations: send alerts to an Arcanna.ai job, read the AI decision, confidence and bucket state back, and return analyst feedback to keep the model learning.

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

### Configuration variables

This table lists the configuration variables required to operate Arcanna.ai. These variables are specified when configuring a Arcanna.ai asset in Splunk SOAR.

VARIABLE | REQUIRED | TYPE | DESCRIPTION
-------- | -------- | ---- | -----------
**base_url** | required | string | Arcanna.ai API base URL (for example https://arcanna.example.com) |
**api_key** | required | password | Arcanna API key (sent as the x-arcanna-api-key header) |
**verify_server_cert** | optional | boolean | Verify the server TLS certificate |
**default_job_id** | optional | numeric | Default Arcanna job id used when an action is run without one |
**default_storage_name** | optional | string | Storage name (or storage tag) of the job's REST input, used when an action is run without one; needed when the API key reaches several storages of a job |
**timeout** | optional | numeric | HTTP timeout in seconds |

### Supported Actions

[test connectivity](#action-test-connectivity) - Validate the asset configuration: the v2 health endpoint must answer status OK for the API key, then the jobs are listed. <br>
[list jobs](#action-list-jobs) - List the Arcanna jobs visible to the API key <br>
[get job](#action-get-job) - Get one Arcanna job by id (title, category, status) <br>
[send event](#action-send-event) - Send one event (alert) to an Arcanna job for a decision; returns the Arcanna event id to poll with 'get event' <br>
[get event](#action-get-event) - Read the Arcanna decision for an event: decision label and value, confidence, bucket state, outlier and processing status <br>
[send feedback](#action-send-feedback) - Return the analyst's verdict on an event to Arcanna (feedback the model learns from) <br>
[get job by name](#action-get-job-by-name) - Get an Arcanna job by its exact title <br>
[list labels](#action-list-labels) - List the labels (decisions) of an Arcanna job; send feedback accepts only these <br>
[get outliers](#action-get-outliers) - List the outlier events of an Arcanna job <br>
[get job metrics](#action-get-job-metrics) - Read the performance metrics of an Arcanna job <br>
[start job](#action-start-job) - Start an Arcanna job <br>
[stop job](#action-stop-job) - Stop an Arcanna job <br>
[train job](#action-train-job) - Start a training run of an Arcanna job (changes the model that scores production events) <br>
[export event](#action-export-event) - Export an event with its decision data from Arcanna <br>
[get reasoning](#action-get-reasoning) - Read the summarised reasoning behind an Arcanna decision <br>
[reprocess event](#action-reprocess-event) - Ask Arcanna to decide an event again <br>
[get api scopes](#action-get-api-scopes) - List the API scopes granted to the configured key <br>
[query events](#action-query-events) - Query events with their decisions (most recent first) across the given jobs or every job the key can read; filter by event ids, date range or Arcanna filters <br>
[get platform metrics](#action-get-platform-metrics) - Read the Arcanna platform and storage-cluster metrics (capacity and health overview)

## action: 'test connectivity'

Validate the asset configuration: the v2 health endpoint must answer status OK for the API key, then the jobs are listed.

Type: **test** <br>
Read only: **True**

Basic test for app.

#### Action Parameters

No parameters are required for this action

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.status | string | | success failure |
action_result.message | string | | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'list jobs'

List the Arcanna jobs visible to the API key

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

No parameters are required for this action

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.status | string | | success failure |
action_result.message | string | | |
action_result.data.\*.job_id | numeric | `arcanna job id` | |
action_result.data.\*.title | string | | |
action_result.data.\*.category | string | | |
action_result.data.\*.status | string | | |
action_result.summary.total_jobs | numeric | | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'get job'

Get one Arcanna job by id (title, category, status)

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**job_id** | optional | Arcanna job id (defaults to the asset's default job id) | numeric | `arcanna job id` |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.status | string | | success failure |
action_result.message | string | | |
action_result.parameter.job_id | numeric | `arcanna job id` | |
action_result.data.\*.job_id | numeric | `arcanna job id` | |
action_result.data.\*.title | string | | |
action_result.data.\*.category | string | | |
action_result.data.\*.status | string | | |
action_result.summary.job_id | numeric | `arcanna job id` | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'send event'

Send one event (alert) to an Arcanna job for a decision; returns the Arcanna event id to poll with 'get event'

Type: **generic** <br>
Read only: **False**

The event body is a JSON object with the fields the job was trained on; a datapath such as artifact:\*.cef can be given directly. One event is sent per run: narrow the datapath with a filter block when a container holds several artifacts. The title is stored with the event.

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**job_id** | optional | Arcanna job id (defaults to the asset's default job id) | numeric | `arcanna job id` |
**title** | required | Event title (for example the alert name) | string | |
**event_json** | required | The event as a JSON object: a JSON string, or a playbook datapath to the fields (for example artifact:\*.cef) | string | |
**storage_name** | optional | Storage name or storage tag of the event (defaults to the asset's default storage name; leave empty when the API key reaches one storage of the job) | string | `arcanna storage tag` |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.status | string | | success failure |
action_result.message | string | | |
action_result.parameter.job_id | numeric | `arcanna job id` | |
action_result.parameter.title | string | | |
action_result.parameter.event_json | string | | |
action_result.parameter.storage_name | string | `arcanna storage tag` | |
action_result.data.\*.event_id | string | `arcanna event id` | |
action_result.data.\*.job_id | numeric | `arcanna job id` | |
action_result.data.\*.storage_tag | string | `arcanna storage tag` | |
action_result.data.\*.status | string | | |
action_result.data.\*.ingest_timestamp | string | | |
action_result.data.\*.error_message | string | | |
action_result.summary.event_id | string | `arcanna event id` | |
action_result.summary.job_id | numeric | `arcanna job id` | |
action_result.summary.status | string | | |
action_result.summary.storage_tag | string | `arcanna storage tag` | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'get event'

Read the Arcanna decision for an event: decision label and value, confidence, bucket state, outlier and processing status

Type: **investigate** <br>
Read only: **True**

The event is finished when Arcanna's result is set and is not 'no_decision' ('No decision' is the label shown while inference is pending). Ingestion is asynchronous, so an event read right after send event can be briefly unknown: it is read again until it appears. With 'max_wait' greater than zero the action reads every 'poll_interval' seconds until a decision or until the wait expires; with 0 it reads once (use a playbook loop for long waits). The action fails when the event is still unknown at the end of the wait.

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**job_id** | optional | Arcanna job id (defaults to the asset's default job id) | numeric | `arcanna job id` |
**event_id** | required | Arcanna event id returned by 'send event' | string | `arcanna event id` |
**max_wait** | optional | Seconds to wait for a final decision, 0 to 300 (0 = read once) | numeric | |
**poll_interval** | optional | Seconds between polls while waiting | numeric | |
**storage_name** | optional | Storage name or storage tag of the event (defaults to the asset's default storage name; leave empty when the API key reaches one storage of the job) | string | `arcanna storage tag` |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.status | string | | success failure |
action_result.message | string | | |
action_result.parameter.job_id | numeric | `arcanna job id` | |
action_result.parameter.event_id | string | `arcanna event id` | |
action_result.parameter.max_wait | numeric | | |
action_result.parameter.poll_interval | numeric | | |
action_result.parameter.storage_name | string | `arcanna storage tag` | |
action_result.data.\*.event_id | string | `arcanna event id` | |
action_result.data.\*.status | string | | |
action_result.data.\*.storage_tag | string | `arcanna storage tag` | |
action_result.data.\*.result_label | string | | |
action_result.data.\*.result | string | | |
action_result.data.\*.confidence_score | numeric | | |
action_result.data.\*.bucket_state | string | | |
action_result.data.\*.outlier | boolean | | True False |
action_result.data.\*.ingest_timestamp | string | | |
action_result.data.\*.error_message | string | | |
action_result.data.\*.knowledge_base_state | string | | |
action_result.data.\*.final | boolean | | True False |
action_result.summary.event_id | string | `arcanna event id` | |
action_result.summary.job_id | numeric | `arcanna job id` | |
action_result.summary.final | boolean | | True False |
action_result.summary.result_label | string | | |
action_result.summary.result | string | | |
action_result.summary.confidence_score | numeric | | |
action_result.summary.bucket_state | string | | |
action_result.summary.outlier | boolean | | True False |
action_result.summary.status | string | | |
action_result.summary.polls | numeric | | |
action_result.summary.waited_seconds | numeric | | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'send feedback'

Return the analyst's verdict on an event to Arcanna (feedback the model learns from)

Type: **generic** <br>
Read only: **False**

The label must be one of the job's labels (see list labels), spelled exactly as in Arcanna. Create the job labels to mirror the SOAR closing statuses; no translation is done.

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**job_id** | optional | Arcanna job id (defaults to the asset's default job id) | numeric | `arcanna job id` |
**event_id** | required | Arcanna event id | string | `arcanna event id` |
**label** | required | One of the job's labels, identical to the SOAR closing status | string | |
**username** | optional | SOAR user who closed the case (for example the container owner); empty attributes the feedback to the API key's user | string | |
**storage_name** | optional | Storage name or storage tag of the event (defaults to the asset's default storage name; leave empty when the API key reaches one storage of the job) | string | `arcanna storage tag` |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.status | string | | success failure |
action_result.message | string | | |
action_result.parameter.job_id | numeric | `arcanna job id` | |
action_result.parameter.event_id | string | `arcanna event id` | |
action_result.parameter.label | string | | |
action_result.parameter.username | string | | |
action_result.parameter.storage_name | string | `arcanna storage tag` | |
action_result.data.\*.status | string | | |
action_result.summary.arcanna_label | string | | |
action_result.summary.username | string | `user name` | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'get job by name'

Get an Arcanna job by its exact title

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**job_name** | required | Exact job title | string | |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.status | string | | success failure |
action_result.message | string | | |
action_result.parameter.job_name | string | | |
action_result.data.\*.job_id | numeric | `arcanna job id` | |
action_result.data.\*.title | string | | |
action_result.data.\*.category | string | | |
action_result.data.\*.status | string | | |
action_result.summary.job_id | numeric | `arcanna job id` | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'list labels'

List the labels (decisions) of an Arcanna job; send feedback accepts only these

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**job_id** | optional | Arcanna job id (defaults to the asset's default job id) | numeric | `arcanna job id` |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.status | string | | success failure |
action_result.message | string | | |
action_result.parameter.job_id | numeric | `arcanna job id` | |
action_result.data.\*.label | string | | |
action_result.summary.total_labels | numeric | | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'get outliers'

List the outlier events of an Arcanna job

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**job_id** | optional | Arcanna job id (defaults to the asset's default job id) | numeric | `arcanna job id` |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.status | string | | success failure |
action_result.message | string | | |
action_result.parameter.job_id | numeric | `arcanna job id` | |
action_result.data.\*.event_id | string | `arcanna event id` | |
action_result.data.\*.event_url | string | `url` | |
action_result.data.\*.bucket_id | string | | |
action_result.data.\*.bucket_url | string | `url` | |
action_result.summary.total_outliers | numeric | | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'get job metrics'

Read the performance metrics of an Arcanna job

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**job_id** | optional | Arcanna job id (defaults to the asset's default job id) | numeric | `arcanna job id` |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.status | string | | success failure |
action_result.message | string | | |
action_result.parameter.job_id | numeric | `arcanna job id` | |
action_result.data.\*.total_events | numeric | | |
action_result.data.\*.total_events_in_knowledge_base | numeric | | |
action_result.data.\*.total_events_with_consensus | numeric | | |
action_result.data.\*.time_saved_minutes | numeric | | |
action_result.data.\*.active_model_id | string | | |
action_result.data.\*.start_time | string | | |
action_result.data.\*.end_time | string | | |
action_result.summary.job_id | numeric | `arcanna job id` | |
action_result.summary.total_events | numeric | | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'start job'

Start an Arcanna job

Type: **generic** <br>
Read only: **False**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**job_id** | optional | Arcanna job id (defaults to the asset's default job id) | numeric | `arcanna job id` |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.status | string | | success failure |
action_result.message | string | | |
action_result.parameter.job_id | numeric | `arcanna job id` | |
action_result.data.\*.status | string | | |
action_result.summary.job_id | numeric | `arcanna job id` | |
action_result.summary.command | string | | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'stop job'

Stop an Arcanna job

Type: **generic** <br>
Read only: **False**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**job_id** | optional | Arcanna job id (defaults to the asset's default job id) | numeric | `arcanna job id` |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.status | string | | success failure |
action_result.message | string | | |
action_result.parameter.job_id | numeric | `arcanna job id` | |
action_result.data.\*.status | string | | |
action_result.summary.job_id | numeric | `arcanna job id` | |
action_result.summary.command | string | | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'train job'

Start a training run of an Arcanna job (changes the model that scores production events)

Type: **generic** <br>
Read only: **False**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**job_id** | optional | Arcanna job id (defaults to the asset's default job id) | numeric | `arcanna job id` |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.status | string | | success failure |
action_result.message | string | | |
action_result.parameter.job_id | numeric | `arcanna job id` | |
action_result.data.\*.status | string | | |
action_result.summary.job_id | numeric | `arcanna job id` | |
action_result.summary.command | string | | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'export event'

Export an event with its decision data from Arcanna

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**job_id** | optional | Arcanna job id (defaults to the asset's default job id) | numeric | `arcanna job id` |
**event_id** | required | Arcanna event id | string | `arcanna event id` |
**storage_name** | optional | Storage name or storage tag of the event (defaults to the asset's default storage name; leave empty when the API key reaches one storage of the job) | string | `arcanna storage tag` |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.status | string | | success failure |
action_result.message | string | | |
action_result.parameter.job_id | numeric | `arcanna job id` | |
action_result.parameter.event_id | string | `arcanna event id` | |
action_result.parameter.storage_name | string | `arcanna storage tag` | |
action_result.data.\*.event_id | string | `arcanna event id` | |
action_result.data.\*.status | string | | |
action_result.data.\*.ingest_timestamp | string | | |
action_result.data.\*.storage_tag | string | `arcanna storage tag` | |
action_result.summary.event_id | string | `arcanna event id` | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'get reasoning'

Read the summarised reasoning behind an Arcanna decision

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**job_id** | optional | Arcanna job id (defaults to the asset's default job id) | numeric | `arcanna job id` |
**event_id** | required | Arcanna event id | string | `arcanna event id` |
**storage_name** | optional | Storage name or storage tag of the event (defaults to the asset's default storage name; leave empty when the API key reaches one storage of the job) | string | `arcanna storage tag` |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.status | string | | success failure |
action_result.message | string | | |
action_result.parameter.job_id | numeric | `arcanna job id` | |
action_result.parameter.event_id | string | `arcanna event id` | |
action_result.parameter.storage_name | string | `arcanna storage tag` | |
action_result.data.\*.reasoning.text | string | | |
action_result.data.\*.reasoning.processing_status | string | | |
action_result.data.\*.reasoning.error | string | | |
action_result.data.\*.summarization.text | string | | |
action_result.data.\*.summarization.processing_status | string | | |
action_result.data.\*.summarization.error | string | | |
action_result.summary.event_id | string | `arcanna event id` | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'reprocess event'

Ask Arcanna to decide an event again

Type: **generic** <br>
Read only: **False**

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**job_id** | optional | Arcanna job id (defaults to the asset's default job id) | numeric | `arcanna job id` |
**event_id** | required | Arcanna event id | string | `arcanna event id` |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.status | string | | success failure |
action_result.message | string | | |
action_result.parameter.job_id | numeric | `arcanna job id` | |
action_result.parameter.event_id | string | `arcanna event id` | |
action_result.data.\*.request.status | string | | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'get api scopes'

List the API scopes granted to the configured key

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

No parameters are required for this action

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.status | string | | success failure |
action_result.message | string | | |
action_result.data.\*.scope | string | | |
action_result.summary.total_scopes | numeric | | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'query events'

Query events with their decisions (most recent first) across the given jobs or every job the key can read; filter by event ids, date range or Arcanna filters

Type: **investigate** <br>
Read only: **True**

At least one of job ids, event ids, size, filters, start date or end date must be given. The asset's default job id is not applied: without job ids Arcanna searches every job and storage the API key may read. Results are sorted by @timestamp, newest first; use page and the has_more summary to read further pages.

#### Action Parameters

PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**job_ids** | optional | Arcanna job ids (a list, or comma separated text); empty searches every job (and every storage) the API key can read | string | `arcanna job id` |
**event_ids** | optional | Comma separated Arcanna event ids | string | `arcanna event id` |
**size** | optional | Maximum number of events (default 50) | numeric | |
**start_date** | optional | Start of the time range (ISO 8601 or Elasticsearch date math such as now-7d) | string | |
**end_date** | optional | End of the time range (ISO 8601 or date math such as now) | string | |
**filters** | optional | JSON array of filter objects {"field", "operator", "value"}; a single object is accepted. Operators: is, is not, is one of, is not one of, contains, not contains, starts with, not starts with, exists, doesn't exist, less than, less than or equal to, greater than, greater than or equal to | string | |
**page** | optional | Result page, counting from 0 (page * size events are skipped) | numeric | |
**decision_points_only** | optional | Return only event ids and decision points, without the Arcanna decision fields and the raw event | boolean | |

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.status | string | | success failure |
action_result.message | string | | |
action_result.parameter.job_ids | string | `arcanna job id` | |
action_result.parameter.event_ids | string | `arcanna event id` | |
action_result.parameter.size | numeric | | |
action_result.parameter.start_date | string | | |
action_result.parameter.end_date | string | | |
action_result.parameter.filters | string | | |
action_result.parameter.page | numeric | | |
action_result.parameter.decision_points_only | boolean | | |
action_result.data.\*.event_id | string | `arcanna event id` | |
action_result.data.\*.job_id | numeric | `arcanna job id` | |
action_result.data.\*.job_title | string | | |
action_result.data.\*.result_label | string | | |
action_result.data.\*.confidence_score | numeric | | |
action_result.data.\*.bucket_state | string | | |
action_result.data.\*.timestamp | string | | |
action_result.summary.returned | numeric | | |
action_result.summary.total_count | numeric | | |
action_result.summary.page | numeric | | |
action_result.summary.has_more | boolean | | True False |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

## action: 'get platform metrics'

Read the Arcanna platform and storage-cluster metrics (capacity and health overview)

Type: **investigate** <br>
Read only: **True**

#### Action Parameters

No parameters are required for this action

#### Action Output

DATA PATH | TYPE | CONTAINS | EXAMPLE VALUES
--------- | ---- | -------- | --------------
action_result.status | string | | success failure |
action_result.message | string | | |
summary.total_objects | numeric | | 1 |
summary.total_objects_successful | numeric | | 1 |

______________________________________________________________________

Auto-generated Splunk SOAR Connector documentation.

Copyright 2026 Splunk Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations under the License.
