# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`arcannaai` is the Splunk SOAR app (connector) for **Arcanna.ai** ("Trustworthy AI for security operations", https://arcanna.ai/,
built by Siscale). Playbooks send alerts to an Arcanna job, read the AI decision (label, confidence, reasoning) back, and
return the analyst's verdict as feedback so the model keeps learning.

- Targets **Arcanna 1.93.0** through its public REST API (the *exposer*), header `x-arcanna-api-key`.
- Built on the **Splunk SOAR SDK** (`splunk-soar-sdk`, Python 3.13, SOAR 7.0+), as Splunk asked when creating the
  repo. The legacy `BaseConnector` version (1.0.2) lives only in the working copy. HTTP via `httpx` (an SDK dependency).
- Every route, request body and response field was checked against the 1.93.0 exposer source, and the app was
  tested on a live Splunk SOAR + Arcanna 1.93.0 instance.
- Current app version `1.0.2` (`pyproject.toml`), `appid` `4c1f3f2e-0f6e-4d2a-9b1c-6a7d2e5b9a31` — never change the
  appid (existing installs upgrade by it).

## This repo vs the working copy

- This repo: `git@github.com:splunk-soar-connectors/arcannaai.git`, created from the org's connector template
  (Apache 2.0 `LICENSE`, `.pre-commit-config.yaml`, `pyproject.toml`, `.github/workflows/*`). Contributions go as a
  PR from a branch to `main`; merging to `main` triggers the org publish workflow (semantic release + Splunkbase).
- Working copy where the app was developed and packaged by hand: `~/CODE/siscale/splunk/arcannaai/` (plus the built
  `~/CODE/siscale/splunk/arcannaai.tgz`). It also holds the playbook sources (`Arcanna_AI_Decision.{json,py}`,
  `Arcanna_AI_Feedback.{json,py}`), the old MIT `LICENSE` and `NOTICE`, which are **not** in this repo (see Open items).
- The working copy is the legacy 1.0.2 connector; this repo is the SDK port. Actions, parameters, asset settings,
  output datapaths, `contains` and messages were kept identical (checked by diffing the generated manifest against the
  1.0.2 JSON), except: failures read `Action failure in <action>: <message>` (SDK prefix), and the dict-valued
  datapaths `arcanna_event`, `arcanna`, `es_cluster_metrics` are no longer declared (the data is still returned).

## License

Apache License 2.0 — the repo's `LICENSE` (from the org template) is kept as is; never replace it with MIT.
Copyright is Splunk's, as in every app of the org: `pyproject.toml` `license = "Copyright (c) 2026 Splunk Inc."`,
every `.py` starts with the Apache header (`# Copyright (c) <years> Splunk Inc.` + license text), `NOTICE` is
generated (with the third-party attributions of the SDK wheels). The `copyright` hook bumps the years — accept it.
Contributor: `authors = [{ name = "marian.craciunescu@arcanna.ai" }]` in `pyproject.toml` (the SDK's manifest
generator leaves `contributors` empty — that is SDK behaviour, not ours).

## Naming

Product name is **Arcanna.ai** (`name`, `product_name`, docs, messages); `product_vendor` stays `Arcanna`.

## Layout (SDK app, same shape as the org's `dnsdb`)

- `pyproject.toml` — project name `arcannaai`, version, license, authors, `splunk-soar-sdk>=7.2.1`,
  `[tool.soar.app] main_module = "src.app:app"`; everything below "YOU SHOULD NOT NEED TO TOUCH" is SDK boilerplate.
  `uv.lock` is committed.
- `src/app.py` — `App(...)` metadata (name `Arcanna.ai`, appid, vendor, logos, `publisher="Arcanna Team"`),
  `test_connectivity`, then `register_actions(app)`.
- `src/asset.py` — `Asset(BaseAsset)`: the six asset fields with `FieldCategory` (connectivity / action);
  `api_key` is `sensitive=True` (rendered as `password`).
- `src/consts.py` — every route, limit, message and shared parameter description. Routes live only here.
- `src/client.py` — `ArcannaClient` (httpx; `x-arcanna-api-key` header; errors ⇒ `ActionFailure`
  `Arcanna returned HTTP {code}: {detail}`; class attribute `transport` is swapped by tests) and helpers `to_int`,
  `int_param`, `resolve_job_id` (param ⇒ asset default ⇒ `MSG_NO_JOB`), `resolve_storage` / `storage_query`,
  `load_json` (JSON or Python-literal datapath object, never eval), `rows`.
- `src/actions/{jobs,events,feedback,platform}.py` — plain functions `(params, soar, asset) -> Output` (directly
  testable). Params/Output/Summary classes sit next to them. Outputs subclass `PermissiveActionOutput` with every
  declared field optional, so the raw Arcanna payload passes through like 1.0.2 and declared fields become datapaths.
  Messages via `soar.set_message`, summaries via `soar.set_summary(<Summary>)`, failures via `raise ActionFailure`.
- `src/actions/__init__.py` — `ACTIONS` table (function, description, verbose, type, read_only, render, summary class)
  and `register_actions`. The action identifier is the function name — never rename one (playbooks call them).
- `tests/test_actions.py` — pytest with `httpx.MockTransport` and a `FakeSoar`; `# given / # when / # then`.
- `manual_readme_content.md` — hand-written docs; `README.md` is regenerated by `build-docs` (manual part + generated
  action reference). `release_notes/` — 1.0.0–1.0.2 history; new notes go to `unreleased.md`.
- Generated, git-ignored: `arcannaai.json` (manifest), `.venv/`, `*.tgz`, `wheels/`.

## Asset configuration

`base_url` (required), `api_key` (required, sent as `x-arcanna-api-key`), `verify_server_cert` (default on),
`default_job_id` (used when an action has no job id; **not** by `query events`), `default_storage_name`, `timeout`
(default 60 s).

## Actions (Arcanna 1.93 routes, see `src/consts.py`)

| Group | Actions | Routes |
|---|---|---|
| Platform | test connectivity, get platform metrics, get api scopes | `GET /api/v2/health/`, `/api/v2/metrics/platform_metrics`, `/api/v2/token/scopes` |
| Jobs | list jobs, get job, get job by name, list labels, start/stop/train job, get outliers, get job metrics | `/api/v1/jobs/...`, `/api/v2/events/{job_id}/outliers`, `/api/v2/metrics/job` |
| Events | send event, get event, export event, get reasoning, reprocess event, query events | `/api/v1/events/...`, `.../export`, `.../get_summarization_reasoning`, `/api/v2/events/{job_id}/{event_id}/reprocess`, `/api/v2/events/query` |
| Feedback | send feedback | `/api/v1/events/{job_id}/{event_id}/feedback` |

Behaviour that matters:

- **test connectivity** fails unless the v2 health endpoint answers status OK for the key.
- **send event** returns the event id and the **storage tag**; severity parameter removed (deprecated by Arcanna).
- **get event** reads again until `max_wait` (capped at `MAX_WAIT_LIMIT` = 300 s, it blocks a SOAR action worker)
  when the event is not stored yet (status `ERROR`) or has no decision (`no_decision`). Still unknown at the end ⇒
  the action fails with `Event X not found in job Y after N s`.
- **send feedback**: the label must be one of the job's labels (checked via list labels, `MSG_BAD_LABEL`). Job labels
  mirror the SOAR closing statuses, so the closing status is sent as-is — **no mapping on the asset** (removed in
  1.0.1). `username` optional; empty ⇒ Arcanna attributes feedback to the API key's user.
- **get job**: single-job route only, no fallback to the list. **get job by name**: server-side exact title match.
- **query events**: `job_ids` (list of ints or comma-separated text); without it every job/storage the key can read is
  searched (asset default job not applied). `filters` must be a list (single object is wrapped). `page`,
  `decision_points_only`; summary has `total_count`, `page`, `has_more`. Newest first.
- Errors are formatted `Arcanna returned HTTP {code}: {detail}` (SOAR shows `Action failure in <action>: ...`). The
  Decision playbook matches substrings (`HTTP 401`, `multiple storages`, `Could not find input integration`) — keep them.
  Nothing is retried silently.
- Removed in 1.0.1 (do not re-add): send bulk events (route gone), add notes, asset feedback mapping, closing notes /
  indicators on feedback (Arcanna ignored them).

### Storages

Each REST input of a job writes to its own storage (storage tag). send event, get event, export event, get reasoning
and send feedback take `storage_name` (display name or tag), else the asset default, else Arcanna resolves it:

- key reaches exactly one storage ⇒ that one;
- several ⇒ HTTP 400 `There are multiple storages associated with this api key...`;
- none ⇒ HTTP 404 `Could not find input integration corresponding to the provided api_key...`.

Always read back on the storage tag the event was sent to.

### Contextual actions

Output `contains` types `arcanna event id`, `arcanna job id`, `arcanna storage tag` drive contextual actions on
artifacts. Keep them stable — the playbooks' typed artifacts depend on them.

## Playbooks (sources live in the working copy, not here)

Not part of this app: no repo in the splunk-soar-connectors org ships playbooks (checked all ~400 repos, none has a
`playbooks/` folder or `.tgz`), and ruff `--fix` would rewrite the generated `.py` and break the JSON hash. The 1.0.2
hand-built archive carried them under `arcannaai/playbooks/*.tgz`; publish them separately (e.g. a PR to
`phantomcyber/playbooks`). They need SOAR running playbooks on Python 3.13.

**Arcanna_AI_Decision**: settings (`ARCANNA_ASSET`, `ARCANNA_STORAGE`, `FIRST_READ_WAIT_SECONDS`=30 capped 300,
`RECORD_HUD_CARD`, `RECORD_ARTIFACT`, ...) → send_event → poll_decision (get event; first read waits inside the app,
then `phantom.LoopState` retries) → decision_check → record_decision → on_finish.

- States: decided, timeout, no decision, send failed, read failed, configuration error (+ pending while polling).
- A read failing with `HTTP 401`, `multiple storages` or `Could not find input integration` is permanent ⇒ `read failed`
  immediately; anything else is retried.
- HUD card colour by outcome, nothing to configure: blue decided (`<label> (NN%)`), red send/read failed or
  configuration error, grey otherwise. Never colour by label text (labels mirror SOAR closing statuses).
- "Arcanna Decision" artifact: identifier `arcanna_decision_<event>_<outcome>`, typed via `field_mapping`
  (event_id/job_id/storage_tag). Outputs include `storage_tag`.

**Arcanna_AI_Feedback**: on a closed container (`REQUIRE_CLOSED`), sends the container status as the label for the
event in the newest "Arcanna Decision" artifact, as the container owner, once per label (an "Arcanna Feedback"
artifact `arcanna_feedback_<event>_<label>_<state>` marks it sent). States: sent, failed, already sent, not closed,
no arcanna event, configuration error.

Export format gotchas (when editing playbooks):

- `.json` `coa.data.nodes[*].userCode` = `"\n"` + the node's custom-code section of the `.py` without its trailing
  newline; `coa.data.hash` = SHA-1 of the `.py`. Edit the `.py`, then sync code + hash into the JSON, or the import
  shows stale code.
- Check after any playbook change on a live SOAR: `phantom.add_artifact(field_mapping=...)`, container `close_time` / `owner_name` via REST,
  running a playbook on a closed container, whether the app installer tolerates a `playbooks/` folder.

## Commands

Toolchain: `uv` and Python 3.13 (`uv python install 3.13`). Pre-commit must run on Python 3.13 (the dev-cicd-tools
v2.3.0 hooks refuse 3.11) — use the one in `.venv`.

```
uv sync                                            # .venv with the SDK + dev tools
.venv/bin/python -m pytest -q tests                # unit tests
git add -A && .venv/bin/pre-commit run --all-files # org hooks; run twice: the first run rewrites files
.venv/bin/soarapps manifests create arcannaai.json .   # generated manifest (git-ignored), to inspect/diff
.venv/bin/soarapps package build -o /tmp/arcannaai.tgz .  # installable package (~37 MB with SDK wheels)
.venv/bin/python -m src.app action get-event -a asset.json -p params.json  # run one action locally
```

`asset.json` holds the asset fields (`base_url`, `api_key`, ...) and contains the key: keep it outside the repo
(only `test_asset.json` is git-ignored). Hooks: ruff + ruff-format (line 88, py313, rules in
`pyproject.toml`), soar-app-linter, mdformat, semgrep, detect-secrets (mark test keys with
`# pragma: allowlist secret`), build-docs, copyright, notice-file, release-notes. There is no `static-tests` hook in
the SDK config, so the appid-registry check of the legacy template no longer runs.

## Org contribution rules (splunk-soar-connectors)

- Conventional Commits (`feat:`, `fix:`, `chore:` ...) — enforced by the commit-msg hook; version bumps come from them.
- One PR per app to `main`. Splunk asked for SOAR SDK apps (`soarapps init` / `soarapps convert`), Python 3.13 only.
- New release notes go to `release_notes/unreleased.md`, not a new version file.
- Everything in the org is Apache 2.0 (this app included).
- Support level: developer-supported by the Arcanna Team.

## Open items before the first PR

1. Splunk said it will update the repo template to an SDK scaffold — after that lands on `main`, rebase and take its
   versions of the boilerplate (`.pre-commit-config.yaml`, `.gitignore`, workflows, pyproject boilerplate).
1. Appid registry: if CI still runs the registry check, Splunk must add `4c1f3f2e-...` / `phantom_arcannaai` /
   `Arcanna.ai` to `phantomcyber/dev-cicd-tools` (PR like #265).
1. Run the SDK build on the live Splunk SOAR + Arcanna 1.93.0 instance (only tested against a fake Arcanna locally).
1. Publish the playbooks separately (see Playbooks).

## Conventions

- NEVER commit on the user's behalf; leave changes for review. Commit messages short, Conventional Commits, no AI
  signature.
- Comments minimal (one-line `#` where needed); never comments about prompt history.
- Never paste, log or echo API keys (the `pragma: allowlist secret` in consts is for the header *name*).
- When a route or payload changes, update `src/consts.py`, the action + its Output class, the tests,
  `manual_readme_content.md` and `release_notes/unreleased.md` together; regenerate the manifest and diff datapaths.
