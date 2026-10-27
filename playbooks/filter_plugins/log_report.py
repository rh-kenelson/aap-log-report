from collections import Counter


def status_counts(jobs):
    return dict(Counter(j.get("status", "unknown") for j in jobs))


def top_failures(jobs, limit=10):
    names = [job_display_name(j) for j in jobs]
    return Counter(names).most_common(limit)


def job_display_name(job):
    sf = job.get("summary_fields", {}) or {}
    for key in ("job_template", "project", "inventory_source", "source_workflow_job", "schedule"):
        obj = sf.get(key)
        if obj and obj.get("name"):
            return obj["name"]
    return job.get("name", "unknown")


def job_display_names(jobs):
    return [job_display_name(j) for j in jobs]


def tail_lines(text, n=60):
    if not text:
        return ""
    lines = text.splitlines()
    return "\n".join(lines[-n:])


def activity_by_operation(entries):
    return dict(Counter(e.get("operation", "unknown") for e in entries))


def activity_by_actor(entries, limit=10):
    actors = []
    for e in entries:
        actor = (e.get("summary_fields", {}) or {}).get("actor")
        actors.append(actor["username"] if actor else "system")
    return Counter(actors).most_common(limit)


class FilterModule(object):
    def filters(self):
        return {
            "status_counts": status_counts,
            "top_failures": top_failures,
            "job_display_name": job_display_name,
            "job_display_names": job_display_names,
            "tail_lines": tail_lines,
            "activity_by_operation": activity_by_operation,
            "activity_by_actor": activity_by_actor,
        }
