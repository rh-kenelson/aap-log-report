# AAP Log & Audit Report

Scheduled AAP job that pulls job-run logs and the platform activity stream (audit
trail) for a configurable window via the Controller API, and emails a
reporting/compliance digest. Built for customer reporting requirements where
AAP's own job history and activity stream are not a durable record (both are
subject to AAP's internal retention/cleanup) — the emailed JSON attachments are
the archival copy.

## What it does

`playbooks/generate_log_report.yml`:

1. Computes a cutoff timestamp `report_lookback_hours` back from now (default 168h / weekly).
2. Queries `GET /api/controller/v2/unified_jobs/?finished__gte=<cutoff>` — every job run
   (job template runs, project/inventory syncs, workflow jobs) in the window.
3. Queries `GET /api/controller/v2/activity_stream/?timestamp__gte=<cutoff>` — the audit
   trail of config/object changes and launches in the window.
4. Pulls a truncated stdout tail (last `failed_stdout_tail_lines`, default 60) for the
   most recent `max_failed_detail` (default 15) failed/error/canceled jobs.
5. Renders `templates/report_email.html.j2` — status breakdown, top-failing templates,
   failed-job stdout excerpts with links back into the AAP UI, audit-trail operation/actor
   breakdowns.
6. Emails the HTML report via `community.general.mail`, with the full job-run and
   activity-stream JSON attached (the actual compliance record).

Both API queries use a single page (`page_size`, default 200). If a window returns more
results than that, the report says so explicitly rather than silently dropping data —
shorten `report_lookback_hours` or run more often if that happens.

## Survey variables

| Variable | Default | Notes |
|---|---|---|
| `report_lookback_hours` | `168` | Reporting window size, in hours |
| `recipient_email` | `kenelson@redhat.com` | Report recipient |

## Required credentials on the job template

1. **SMTP Relay (Gmail)** (id 26 on `192.168.3.215`, existing — reused from the AAP
   Release Digest project). Injects `SMTP_HOST/PORT/USERNAME/PASSWORD/SECURE/FROM`; the
   email task is skipped (not failed) if `SMTP_HOST` isn't set, so the report still
   generates without it.
2. **A "Red Hat Ansible Automation Platform" credential**, so the job can call back into
   its own Controller API. **This one has to be created by hand in the AAP UI** (not by
   this automation) because it needs a real OAuth token value:
   - Access Management → Credentials → Add → type "Red Hat Ansible Automation Platform"
   - Name: `AAP Self-API (Log Report)`
   - Red Hat Ansible Automation Platform (host): `https://192.168.3.215`
   - OAuth Token: a token for a read-only/limited account if your RBAC supports scoping
     one; otherwise a personal access token is fine since this only ever does `GET`
     requests against jobs/activity_stream/stdout.
   - Verify SSL: off, unless the EE's CA bundle trusts this instance's cert.
   - Attach it to the **AAP Log & Audit Report** job template.

   This credential injects `aap_hostname`/`aap_token`/`aap_validate_certs` as extra_vars,
   which the playbook reads directly — no extra wiring needed once it's attached.

## Scheduling vs. AAP's own cleanup jobs

The report is scheduled for **Sundays 20:00 UTC**, deliberately ahead of this AAP
instance's built-in cleanup system jobs:

| Cleanup job | Deletes data older than | Runs |
|---|---|---|
| Cleanup Job Details | 120 days | Sundays 21:54 UTC |
| Cleanup Activity Stream | 355 days | Tuesdays 21:54 UTC |

In practice neither retention window is anywhere near as short as the weekly report
cadence, so no data the report would ever capture is actually at risk under normal
operation — but the ordering is correct regardless, and matters more if retention is
ever shortened later (e.g. to save DB size). If those cleanup schedules change on this
instance, re-check this ordering; `schedule_rrule` in `setup/provision_aap.yml` is the
single place to adjust it (the provisioning playbook keeps a live schedule's `rrule` in
sync with that var on re-run).

## Provisioning

`setup/provision_aap.yml` is a one-time (re-runnable/idempotent) playbook that creates the
AAP Project, Job Template + survey, and a weekly schedule via the `ansible.controller`
collection + raw Controller API calls (the `ansible.controller.schedule` module is known
buggy against this AAP 2.7/4.8.4 backend — see the AAP Release Digest project notes —
so schedule creation goes straight to the raw REST API). It does **not** create the
self-API credential (see above) — if that credential doesn't exist yet when this runs,
it creates everything else and prints a reminder instead of failing.

Run it with the Controller host/token supplied via a gitignored extra-vars file, never
inline on the command line:

```
ansible-playbook setup/provision_aap.yml -e @/path/to/secrets.yml
```

where `secrets.yml` contains:

```yaml
controller_host: "https://192.168.3.215"
controller_oauthtoken: "<AAP API token>"
controller_validate_certs: false
```

## Collections

`collections/requirements.yml` pins `community.general` (for `community.general.mail`) —
AAP's default execution environment doesn't ship it, so it's installed automatically
during project SCM sync.
