"""Collect and calculate Lab 10 CI/CD metrics; no workflow is triggered.

AI assistance: Codex (implementation and tests). See docs/ci-cd/README.md.
Python 3.11+, standard library; Windows may additionally need tzdata.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen
from zoneinfo import ZoneInfo

WORKFLOWS = (
    "CI",
    "Static analysis",
    "Lab07 card ordering",
    "Lab08 characterization tests",
    "Generate and Deploy API Docs",
)
FAILURES = {"failure", "timed_out", "action_required", "startup_failure", "stale"}
UTC = timezone.utc


def dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def iso(value):
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def minutes(start, end):
    return (dt(end) - dt(start)).total_seconds() / 60


def stats(values):
    values = [v for v in values if v is not None]
    return {
        "count": len(values),
        "mean": statistics.mean(values) if values else None,
        "median": statistics.median(values) if values else None,
        "max": max(values) if values else None,
    }


def selected(source, keys):
    return {key: source.get(key) for key in keys.split()}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")


def get_token(use_git=False):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token.strip()
    if shutil.which("gh"):
        result = subprocess.run(
            ["gh", "auth", "token", "--hostname", "github.com"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    if use_git:
        result = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"},
        )
        if result.returncode:
            raise ValueError(
                "GitHub credential unavailable; use GH_TOKEN or gh auth login"
            )
        fields = dict(
            line.split("=", 1) for line in result.stdout.splitlines() if "=" in line
        )
        if fields.get("password"):
            return fields["password"]
        raise ValueError("Git credential helper did not return a GitHub credential")
    return None


class GitHub:
    """Read-only API client. Tokens are never persisted or printed."""

    def __init__(self, repo, token=None):
        self.root = f"https://api.github.com/repos/{repo}"
        self.token = token

    def get(self, endpoint, params=None):
        url = self.root + endpoint
        if params:
            url += "?" + urlencode(params)
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Monkey-Business-Lab10-metrics",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        try:
            with urlopen(Request(url, headers=headers), timeout=60) as response:
                return json.load(response)
        except HTTPError as exc:
            # Never include headers, signed URLs or credential-helper output.
            raise ValueError(f"GitHub API HTTP {exc.code}: {endpoint}") from None

    def pages(self, endpoint, key=None, params=None):
        items = []
        page = 1
        while True:
            data = self.get(endpoint, {**(params or {}), "per_page": 100, "page": page})
            if (
                isinstance(data, dict)
                and data.get("total_count", 0) > 1000
                and endpoint == "/actions/runs"
            ):
                raise ValueError(
                    "More than 1,000 runs in query; split the reporting period"
                )
            batch = data[key] if key else data
            items.extend(batch)
            if len(batch) < 100:
                return items
            page += 1

    def failure_log(self, job_id):
        """Retain error context only; never forward auth to the log storage host."""

        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        endpoint = f"/actions/jobs/{job_id}/logs"
        headers = {"User-Agent": "Monkey-Business-Lab10-metrics"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = Request(self.root + endpoint, headers=headers)
        try:
            with build_opener(NoRedirect).open(request, timeout=60) as response:
                text = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            if exc.code != 302:
                return {"source": endpoint, "available": False, "http_status": exc.code}
            location = exc.headers["Location"]
            if not location.startswith("https://"):
                raise ValueError("Refusing non-HTTPS log redirect")
            try:
                with urlopen(location, timeout=60) as response:
                    text = response.read().decode("utf-8", errors="replace")
            except HTTPError as log_error:
                return {
                    "source": endpoint,
                    "available": False,
                    "http_status": log_error.code,
                    "stage": "log_storage",
                }
        lines = text.splitlines()
        indices = set()
        for i, line in enumerate(lines):
            if re.search(
                r"error|failed|assertion|traceback|exit code|would reformat", line, re.I
            ):
                indices.update(range(max(0, i - 2), min(len(lines), i + 4)))
        excerpts = [lines[i] for i in sorted(indices)][:100]
        return {
            "source": endpoint,
            "available": True,
            "excerpt": excerpts,
            "log_lines": len(lines),
        }


def collect(api, start, end, tz_name, workflows):
    """Fetch all pages, all attempts, job timestamps and PR commit dates."""
    window = f"{iso(start)}..{iso(end - timedelta(seconds=1))}"
    initial = api.pages(
        "/actions/runs",
        "workflow_runs",
        {
            "branch": "main",
            "event": "push",
            "created": window,
        },
    )
    shas = sorted({r["head_sha"] for r in initial if r["name"] in workflows})
    evidence = {
        "schema_version": 1,
        "repository": api.root.split("/repos/", 1)[1],
        "branch": "main",
        "event": "push",
        "timezone": tz_name,
        "window_utc": {"from": iso(start), "to_exclusive": iso(end)},
        "collected_at": iso(datetime.now(UTC)),
        "workflows": list(workflows),
        "runs": [],
        "changes": {},
        "ancestry": {},
    }
    for index, sha in enumerate(shas, 1):
        print(f"Collecting commit {index}/{len(shas)} {sha[:7]}", flush=True)
        # Fetch the complete workflow cohort, including boundary-straddling runs.
        runs = api.pages(
            "/actions/runs",
            "workflow_runs",
            {
                "branch": "main",
                "event": "push",
                "head_sha": sha,
            },
        )
        runs = [r for r in runs if r["name"] in workflows]
        if not runs or not start <= min(dt(r["created_at"]) for r in runs) < end:
            continue
        for run in sorted(runs, key=lambda r: (r["created_at"], r["id"])):
            for attempt in range(1, run["run_attempt"] + 1):
                detail = api.get(f"/actions/runs/{run['id']}/attempts/{attempt}")
                jobs = api.pages(
                    f"/actions/runs/{run['id']}/attempts/{attempt}/jobs", "jobs"
                )
                record = selected(
                    detail,
                    "id name head_sha head_branch event status conclusion run_attempt "
                    "created_at run_started_at updated_at html_url workflow_id",
                )
                record["jobs"] = [
                    selected(
                        j,
                        "id name status conclusion started_at completed_at html_url "
                        "check_run_url steps",
                    )
                    for j in jobs
                ]
                for job in record["jobs"]:
                    if job["conclusion"] in FAILURES:
                        job["failure_log"] = api.failure_log(job["id"])
                        check_url = job.get("check_run_url")
                        if check_url and check_url.startswith(
                            api.root + "/check-runs/"
                        ):
                            job["annotations"] = api.pages(
                                check_url[len(api.root) :] + "/annotations"
                            )
                evidence["runs"].append(record)
        prs = api.pages(f"/commits/{sha}/pulls")
        prs = [
            p
            for p in prs
            if p.get("merged_at")
            and p["base"]["ref"] == "main"
            and p.get("merge_commit_sha") == sha
        ]
        if len(prs) > 1:
            raise ValueError(f"Ambiguous merged PR for {sha}")
        commit = api.get(f"/commits/{sha}")
        change = {
            "sha": sha,
            "commit_url": commit["html_url"],
            "authored_at": commit["commit"]["author"]["date"],
            "committed_at": commit["commit"]["committer"]["date"],
            "parents": [p["sha"] for p in commit["parents"]],
            "pr": None,
        }
        if prs:
            pr = api.get(f"/pulls/{prs[0]['number']}")
            commits = api.pages(f"/pulls/{pr['number']}/commits")
            if len(commits) != pr["commits"]:
                raise ValueError(f"Incomplete commit history for PR #{pr['number']}")
            change["pr"] = selected(
                pr, "number html_url created_at merged_at merge_commit_sha"
            )
            change["pr"]["commits"] = [
                {
                    "sha": c["sha"],
                    "authored_at": c["commit"]["author"]["date"],
                    "committed_at": c["commit"]["committer"]["date"],
                }
                for c in commits
            ]
        change["first_commit_at"] = (
            change["pr"]["commits"][0]["authored_at"] if prs else change["authored_at"]
        )
        evidence["changes"][sha] = change
    enrich_ancestry(api, evidence)
    return evidence


def enrich_ancestry(api, evidence):
    """Check earlier green descendants, including overlapping successful CI."""
    preliminary = calculate(evidence)
    for row in preliminary["records"]:
        for candidate in preliminary["records"]:
            green = candidate["green_at"]
            if (
                candidate["sha"] == row["sha"]
                or not green
                or dt(green) < dt(row["created_at"])
                or (row["green_at"] and dt(green) >= dt(row["green_at"]))
            ):
                continue
            key = f"{row['sha']}...{candidate['sha']}"
            if key not in evidence["ancestry"]:
                comparison = api.get(f"/compare/{key}")
                evidence["ancestry"][key] = comparison["status"]


def run_times(run):
    jobs = [
        j
        for j in run["jobs"]
        if j.get("started_at")
        and j.get("completed_at")
        and j.get("conclusion") != "skipped"
    ]
    if run["status"] != "completed":
        return None
    if not jobs:
        return {
            "started_at": None,
            "completed_at": run["updated_at"],
            "queue_minutes": None,
            "execution_minutes": None,
            "completion_source": "updated_at_fallback",
        }
    if any(j["status"] != "completed" for j in run["jobs"]):
        return None
    started = min(j["started_at"] for j in jobs)
    finished = max(j["completed_at"] for j in jobs)
    # created_at belongs to attempt 1; GitHub does not expose the rerun request
    # timestamp here. Do not label time between attempts as runner queue.
    queue = minutes(run["created_at"], started) if run["run_attempt"] == 1 else None
    return {
        "started_at": started,
        "completed_at": finished,
        "completion_source": "jobs.completed_at",
        "queue_minutes": queue,
        "execution_minutes": minutes(started, finished),
    }


def active_minutes(runs, start, end):
    """Union of job intervals: overlapping jobs must not count twice."""
    if not start or not end:
        return None
    lower, upper = dt(start), dt(end)
    intervals = sorted(
        (max(dt(j["started_at"]), lower), min(dt(j["completed_at"]), upper))
        for r in runs
        for j in r["jobs"]
        if j.get("started_at")
        and j.get("completed_at")
        and j.get("conclusion") != "skipped"
        and dt(j["started_at"]) < upper
        and dt(j["completed_at"]) > lower
    )
    total = 0.0
    cursor = lower
    for begin, finish in intervals:
        total += max(0, (finish - max(begin, cursor)).total_seconds())
        cursor = max(cursor, finish)
    return total / 60


def calculate(evidence):
    start, end = (dt(evidence["window_utc"][k]) for k in ("from", "to_exclusive"))
    grouped = defaultdict(list)
    warnings = []
    timing = []
    for run in evidence["runs"]:
        if (
            run["name"] not in evidence["workflows"]
            or run["head_branch"] != "main"
            or run["event"] != "push"
        ):
            continue
        grouped[run["head_sha"]].append(run)
    rows = []
    for sha, runs in grouped.items():
        created = min(r["created_at"] for r in runs)
        if not start <= dt(created) < end:
            continue
        workflow_ids = {r["workflow_id"] for r in runs}
        events = []
        first_starts = []
        for run in runs:
            times = run_times(run)
            timing.append(
                {
                    **selected(run, "id name head_sha run_attempt conclusion html_url"),
                    **(
                        times
                        or {
                            "started_at": None,
                            "completed_at": None,
                            "queue_minutes": None,
                            "execution_minutes": None,
                        }
                    ),
                }
            )
            if times and dt(times["completed_at"]) < end:
                events.append((dt(times["completed_at"]), run, times))
                if times.get("completion_source") == "updated_at_fallback":
                    warnings.append(
                        f"No job timestamps: run {run['id']} attempt {run['run_attempt']}; "
                        "completion uses updated_at, queue/execution unknown"
                    )
                if run["run_attempt"] == 1 and times["started_at"]:
                    first_starts.append(times["started_at"])
            elif run["status"] == "completed" and not times:
                warnings.append(
                    f"Missing job timing: run {run['id']} attempt {run['run_attempt']}"
                )
        events.sort(key=lambda e: (e[0], e[1]["id"], e[1]["run_attempt"]))
        current = {}
        green_at = None
        green_events = []
        previous_green = False
        red_at = None
        terminal_at = None
        for finished, run, times in events:
            if run["conclusion"] in FAILURES and red_at is None:
                red_at = iso(finished)
            old = current.get(run["workflow_id"])
            if old is None or (run["created_at"], run["run_attempt"]) >= (
                old["created_at"],
                old["run_attempt"],
            ):
                current[run["workflow_id"]] = run
            if set(current) == workflow_ids:
                terminal_at = iso(finished)
                now_green = all(r["conclusion"] == "success" for r in current.values())
                if now_green and not previous_green:
                    green_events.append(iso(finished))
                    if green_at is None:
                        green_at = iso(finished)
                previous_green = now_green
        change = evidence["changes"][sha]
        first = change["first_commit_at"]
        started = min(first_starts) if first_starts else None
        row = {
            "sha": sha,
            "pr": change["pr"]["number"] if change["pr"] else None,
            "first_commit_at": first,
            "created_at": created,
            "started_at": started,
            "completed_at": terminal_at,
            "green_at": green_at,
            "green_events": green_events,
            "red_at": red_at,
            "status": (
                "incomplete"
                if terminal_at is None
                else (
                    ("red_then_green" if previous_green else "green_then_red")
                    if red_at and green_at
                    else "red" if red_at else "green" if green_at else "other"
                )
            ),
            "queue_minutes": minutes(created, started) if started else None,
            "execution_minutes": (
                minutes(started, green_at or terminal_at)
                if started and terminal_at
                else None
            ),
            "pre_ci_minutes": minutes(first, created),
            "lead_minutes": None,
            "lead_queue_minutes": None,
            "lead_execution_minutes": None,
            "deployed_by": None,
            "run_ids": sorted({r["id"] for r in runs}),
            "workflow_names": sorted({r["name"] for r in runs}),
            "failure_notes": [
                f"{r['name']}/{j['name']}: "
                + (
                    "; ".join(
                        a["message"]
                        for a in j.get("annotations", [])
                        if a["annotation_level"] == "failure"
                    )
                    or "; ".join(
                        s["name"]
                        for s in j.get("steps", [])
                        if s.get("conclusion") in FAILURES
                    )
                    or "див. failure_log у snapshot; причина потребує аналізу"
                )
                for r in runs
                for j in r["jobs"]
                if j["conclusion"] in FAILURES
            ],
            "attempts": [
                {
                    "id": r["id"],
                    "attempt": r["run_attempt"],
                    "conclusion": r["conclusion"],
                    "url": r["html_url"],
                }
                for r in runs
            ],
        }
        row["active_job_minutes"] = active_minutes(
            runs, started, green_at or terminal_at
        )
        row["internal_idle_minutes"] = (
            row["execution_minutes"] - row["active_job_minutes"]
            if row["execution_minutes"] is not None
            and row["active_job_minutes"] is not None
            else None
        )
        rows.append(row)
    rows.sort(key=lambda r: (r["created_at"], r["sha"]))
    greens = sorted((r for r in rows if r["green_at"]), key=lambda r: r["green_at"])
    green_transitions = sorted(
        (
            {"sha": r["sha"], "green_at": when}
            for r in rows
            for when in r["green_events"]
        ),
        key=lambda g: g["green_at"],
    )
    recoveries = []
    for row in rows:
        candidates = [
            g
            for g in greens
            if dt(g["green_at"]) >= dt(row["created_at"])
            and (
                g["sha"] == row["sha"]
                or evidence.get("ancestry", {}).get(f"{row['sha']}...{g['sha']}")
                in {"ahead", "identical"}
            )
        ]
        if candidates:
            deployment = candidates[0]
            row["deployed_by"] = deployment["sha"]
            row["lead_minutes"] = minutes(
                row["first_commit_at"], deployment["green_at"]
            )
            starts = [
                value
                for value in (row["started_at"], deployment["started_at"])
                if value and dt(value) <= dt(deployment["green_at"])
            ]
            lead_started = min(starts, key=dt) if starts else None
            row["lead_queue_minutes"] = (
                minutes(row["created_at"], lead_started) if lead_started else None
            )
            row["lead_execution_minutes"] = (
                minutes(lead_started, deployment["green_at"]) if lead_started else None
            )
            if row["lead_minutes"] < 0 or row["pre_ci_minutes"] < 0:
                raise ValueError(f"Non-monotonic commit timestamps for {row['sha']}")
        if row["red_at"]:
            later = [
                g for g in green_transitions if dt(g["green_at"]) > dt(row["red_at"])
            ]
            recoveries.append(
                {
                    "failed_sha": row["sha"],
                    "red_at": row["red_at"],
                    "green_sha": later[0]["sha"] if later else None,
                    "green_at": later[0]["green_at"] if later else None,
                    "minutes": (
                        minutes(row["red_at"], later[0]["green_at"]) if later else None
                    ),
                }
            )
    completed = [r for r in rows if r["completed_at"]]
    failures = [r for r in completed if r["red_at"]]
    leads = [r for r in rows if r["lead_minutes"] is not None]
    part_sources = {
        "pre_ci_minutes": "pre_ci_minutes",
        "queue_minutes": "lead_queue_minutes",
        "execution_minutes": "lead_execution_minutes",
        "lead_minutes": "lead_minutes",
    }
    parts = {
        key: sum(r[source] for r in leads if r[source] is not None)
        for key, source in part_sources.items()
    }
    total = parts["lead_minutes"]
    parts["shares_percent"] = {
        key: 100 * parts[key] / total if total else None
        for key in ("pre_ci_minutes", "queue_minutes", "execution_minutes")
    }
    weeks = (end - start).total_seconds() / (7 * 86400)
    tz = ZoneInfo(evidence["timezone"])
    days = Counter(dt(r["green_at"]).astimezone(tz).date().isoformat() for r in greens)
    return {
        "repository": evidence["repository"],
        "window_utc": evidence["window_utc"],
        "timezone": evidence["timezone"],
        "workflows": evidence["workflows"],
        "counts": {
            "commits": len(rows),
            "completed_commits": len(completed),
            "green_commits": len(greens),
            "failed_commits": len(failures),
            "workflow_runs": len({r["id"] for runs in grouped.values() for r in runs}),
            "attempts": len(timing),
            "incomplete_commits": len(rows) - len(completed),
        },
        "deployment_frequency_per_week": len(greens) / weeks,
        "change_failure_rate_percent": (
            100 * len(failures) / len(completed) if completed else None
        ),
        "lead_time_minutes": stats(r["lead_minutes"] for r in rows),
        "recovery_time_minutes": stats(r["minutes"] for r in recoveries),
        "unresolved_failures": sum(r["minutes"] is None for r in recoveries),
        "workflow_execution_minutes": stats(
            t["execution_minutes"]
            for t in timing
            if t["completed_at"] and dt(t["completed_at"]) < end
        ),
        "commit_execution_minutes": stats(r["execution_minutes"] for r in leads),
        "lead_time_parts": parts,
        "green_commits_by_day": dict(sorted(days.items())),
        "records": rows,
        "workflow_timings": timing,
        "recoveries": recoveries,
        "warnings": warnings,
    }


def number(value):
    return "н/д" if value is None else f"{value:.2f}"


def render_reports(result, output):
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "metrics-auto.json", result)
    c = result["counts"]
    docs = Path(__file__).resolve().parents[1] / "docs" / "ci-cd"
    readme_link = Path(os.path.relpath(docs / "README.md", output)).as_posix()
    baseline_link = Path(
        os.path.relpath(docs / "evidence/manual-baseline", output)
    ).as_posix()
    lines = [
        "# Автоматичний підрахунок CI/CD",
        "",
        "Згенеровано `scripts/calculate_ci_metrics.py`. "
        f"Методика і команда: [README]({readme_link}).",
        "",
        f"Період UTC: `{result['window_utc']['from']}` ≤ created_at < "
        f"`{result['window_utc']['to_exclusive']}`.",
        f"Час відображення: `{result['timezone']}`. Завершення після верхньої межі не враховано.",
        "",
        f"Комітів: **{c['commits']}**; workflow-запусків: **{c['workflow_runs']}**; "
        f"спроб: **{c['attempts']}**.",
        "",
        "| Метрика | Формула | Результат |",
        "|---|---|---|",
        "| Частота розгортань | зелені коміти / тижні | "
        f"{number(result['deployment_frequency_per_week'])} / тиждень |",
        "| Lead time | перший коміт PR → перший зелений main, який його містить | "
        f"середнє {number(result['lead_time_minutes']['mean'])} хв; "
        f"медіана {number(result['lead_time_minutes']['median'])} хв |",
        f"| Частота збоїв | {c['failed_commits']} / {c['completed_commits']} × 100% | "
        f"{number(result['change_failure_rate_percent'])}% |",
        "| Відновлення | червоний → наступний зелений main | "
        f"середнє {number(result['recovery_time_minutes']['mean'])} хв; "
        f"медіана {number(result['recovery_time_minutes']['median'])} хв |",
        "",
        f"Незавершених комітів: {c['incomplete_commits']}; "
        f"невідновлених збоїв: {result['unresolved_failures']}.",
        "",
        "## Склад lead time",
        "",
        "| Частина | Хвилини | Частка |",
        "|---|---:|---:|",
    ]
    for key, label in (
        ("pre_ci_minutes", "До створення CI"),
        ("queue_minutes", "Початкова черга"),
        ("execution_minutes", "Від першого job до зеленого стану"),
    ):
        lines.append(
            f"| {label} | {number(result['lead_time_parts'][key])} | "
            f"{number(result['lead_time_parts']['shares_percent'][key])}% |"
        )
    lines += [
        "",
        "## Тривалість workflow",
        "",
        "Медіана виконання одного workflow: "
        f"{number(result['workflow_execution_minutes']['median'])} хв; "
        f"максимум: {number(result['workflow_execution_minutes']['max'])} хв.",
        "",
        "## Якість даних",
        "",
    ]
    lines += [f"- {w}" for w in result["warnings"]] or [
        "Пропусків часових даних не виявлено."
    ]
    (output / "metrics-auto.md").write_text("\n".join(lines) + "\n", "utf-8")
    tz = ZoneInfo(result["timezone"])

    def local(value):
        return dt(value).astimezone(tz).strftime("%d.%m %H:%M:%S") if value else "н/д"

    raw = [
        "# Сирі дані CI/CD",
        "",
        "Використання ШІ: Codex — скрипт збору, перерахунок і перевірка даних. "
        f"Попередній ручний розрахунок: [архів]({baseline_link}/).",
        "",
        f"Дані з GitHub Actions API; [методика та відтворення]({readme_link}), "
        f"[автоматичний результат](metrics-auto.md). Час: {result['timezone']}.",
        "",
        f"Період UTC: `{result['window_utc']['from']}` ≤ створення CI < "
        f"`{result['window_utc']['to_exclusive']}`. Workflow: "
        + ", ".join(result["workflows"])
        + ".",
        "",
        "Один рядок — один коміт. Черга — до першого job; виконання — інтервал "
        "від першого job до завершення врахованих workflow. "
        "Він може містити внутрішні очікування.",
        "",
        "| № | Коміт | PR | Перший коміт PR | Запуск завершено | "
        "Черга, хв | Виконання, хв | Статус | Докази | Примітка |",
        "|---|---|---|---|---|---:|---:|---|---|---|",
    ]
    for i, row in enumerate(result["records"], 1):
        base = f"https://github.com/{result['repository']}"
        pr = f"[#{row['pr']}]({base}/pull/{row['pr']})" if row["pr"] else "прямий коміт"
        links = "; ".join(
            f"[{run_id}]({base}/actions/runs/{run_id})" for run_id in row["run_ids"]
        )
        note = "; ".join(row["failure_notes"] or row["workflow_names"])
        note = note.replace("|", "\\|").replace("\n", " ")
        raw.append(
            f"| {i} | [`{row['sha'][:7]}`]({base}/commit/{row['sha']}) | {pr} | "
            f"{local(row['first_commit_at'])} | {local(row['green_at'] or row['completed_at'])} | "
            f"{number(row['queue_minutes'])} | {number(row['execution_minutes'])} | "
            f"{row['status']} | {links} | {note} |"
        )
    (output / "metrics-raw.md").write_text("\n".join(raw) + "\n", "utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="ukma-fin-ssdm-2026/Monkey-Business-project")
    parser.add_argument("--from", dest="start")
    parser.add_argument(
        "--to", dest="end", help="Exclusive local date, e.g. 2026-11-15"
    )
    parser.add_argument("--timezone", default="Europe/Kyiv")
    parser.add_argument(
        "--workflow", action="append", help="Repeat to override the workflow allowlist"
    )
    parser.add_argument(
        "--git-auth",
        action="store_true",
        help="Use the existing github.com Git credential",
    )
    parser.add_argument(
        "--evidence", type=Path, default=Path("docs/ci-cd/evidence/api-snapshot.json")
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Calculate from saved evidence without network access",
    )
    parser.add_argument("--output", type=Path, default=Path("docs/ci-cd"))
    args = parser.parse_args()
    try:
        if args.offline:
            evidence = json.loads(args.evidence.read_text("utf-8"))
        else:
            if not args.start or not args.end:
                parser.error("--from and --to are required for collection")
            tz = ZoneInfo(args.timezone)
            start = (
                datetime.fromisoformat(args.start).replace(tzinfo=tz).astimezone(UTC)
            )
            end = datetime.fromisoformat(args.end).replace(tzinfo=tz).astimezone(UTC)
            if start >= end:
                parser.error("--from must precede --to")
            api = GitHub(args.repo, get_token(args.git_auth))
            evidence = collect(
                api, start, end, args.timezone, args.workflow or WORKFLOWS
            )
            write_json(args.evidence, evidence)
        result = calculate(evidence)
        render_reports(result, args.output)
        print(json.dumps(result["counts"], ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
