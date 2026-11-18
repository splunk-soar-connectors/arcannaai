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

from soar_sdk.app import App

from . import events, feedback, jobs, platform

# (function, description, verbose, action type, read only, render, summary class)
ACTIONS = (
    (
        jobs.list_jobs,
        "List the Arcanna jobs visible to the API key",
        "",
        "investigate",
        True,
        "table",
        jobs.TotalJobsSummary,
    ),
    (
        jobs.get_job,
        "Get one Arcanna job by id (title, category, status)",
        "",
        "investigate",
        True,
        "table",
        jobs.JobSummary,
    ),
    (
        events.send_event,
        "Send one event (alert) to an Arcanna job for a decision; returns the Arcanna event id to poll with 'get event'",
        (
            "The event body is a JSON object with the fields the job was trained on; a datapath such as artifact:*.cef can be given "
            "directly. One event is sent per run: narrow the datapath with a filter block when a container holds several artifacts. "
            "The title is stored with the event."
        ),
        "generic",
        False,
        "table",
        events.SendEventSummary,
    ),
    (
        events.get_event,
        "Read the Arcanna decision for an event: decision label and value, confidence, bucket state, outlier and processing status",
        (
            "The event is finished when Arcanna's result is set and is not 'no_decision' ('No decision' is the label shown while "
            "inference is pending). Ingestion is asynchronous, so an event read right after send event can be briefly unknown: it is "
            "read again until it appears. With 'max_wait' greater than zero the action reads every 'poll_interval' seconds until a "
            "decision or until the wait expires; with 0 it reads once (use a playbook loop for long waits). The action fails when the "
            "event is still unknown at the end of the wait."
        ),
        "investigate",
        True,
        "table",
        events.GetEventSummary,
    ),
    (
        feedback.send_feedback,
        "Return the analyst's verdict on an event to Arcanna (feedback the model learns from)",
        (
            "The label must be one of the job's labels (see list labels), spelled exactly as in Arcanna. Create the job labels to "
            "mirror the SOAR closing statuses; no translation is done."
        ),
        "generic",
        False,
        "table",
        feedback.SendFeedbackSummary,
    ),
    (
        jobs.get_job_by_name,
        "Get an Arcanna job by its exact title",
        "",
        "investigate",
        True,
        "table",
        jobs.JobSummary,
    ),
    (
        jobs.list_labels,
        "List the labels (decisions) of an Arcanna job; send feedback accepts only these",
        "",
        "investigate",
        True,
        "table",
        jobs.TotalLabelsSummary,
    ),
    (
        jobs.get_outliers,
        "List the outlier events of an Arcanna job",
        "",
        "investigate",
        True,
        "table",
        jobs.TotalOutliersSummary,
    ),
    (
        jobs.get_job_metrics,
        "Read the performance metrics of an Arcanna job",
        "",
        "investigate",
        True,
        "json",
        jobs.JobMetricsSummary,
    ),
    (
        jobs.start_job,
        "Start an Arcanna job",
        "",
        "generic",
        False,
        "table",
        jobs.JobCommandSummary,
    ),
    (
        jobs.stop_job,
        "Stop an Arcanna job",
        "",
        "generic",
        False,
        "table",
        jobs.JobCommandSummary,
    ),
    (
        jobs.train_job,
        "Start a training run of an Arcanna job (changes the model that scores production events)",
        "",
        "generic",
        False,
        "table",
        jobs.JobCommandSummary,
    ),
    (
        events.export_event,
        "Export an event with its decision data from Arcanna",
        "",
        "investigate",
        True,
        "table",
        events.EventSummary,
    ),
    (
        events.get_reasoning,
        "Read the summarised reasoning behind an Arcanna decision",
        "",
        "investigate",
        True,
        "table",
        events.EventSummary,
    ),
    (
        events.reprocess_event,
        "Ask Arcanna to decide an event again",
        "",
        "generic",
        False,
        "table",
        None,
    ),
    (
        platform.get_api_scopes,
        "List the API scopes granted to the configured key",
        "",
        "investigate",
        True,
        "table",
        platform.TotalScopesSummary,
    ),
    (
        events.query_events,
        (
            "Query events with their decisions (most recent first) across the given jobs or every job the key can read; "
            "filter by event ids, date range or Arcanna filters"
        ),
        (
            "At least one of job ids, event ids, size, filters, start date or end date must be given. The asset's default job id is "
            "not applied: without job ids Arcanna searches every job and storage the API key may read. Results are sorted by "
            "@timestamp, newest first; use page and the has_more summary to read further pages."
        ),
        "investigate",
        True,
        "table",
        events.QueryEventsSummary,
    ),
    (
        platform.get_platform_metrics,
        "Read the Arcanna platform and storage-cluster metrics (capacity and health overview)",
        "",
        "investigate",
        True,
        "json",
        None,
    ),
)


def register_actions(app: App) -> App:
    for (
        function,
        description,
        verbose,
        action_type,
        read_only,
        render_as,
        summary_type,
    ) in ACTIONS:
        app.action(
            description=description,
            verbose=verbose,
            action_type=action_type,
            read_only=read_only,
            render_as=render_as,
            summary_type=summary_type,
        )(function)
    return app
