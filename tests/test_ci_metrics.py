"""Lab 10 metric semantics, using synthetic fixtures (never real evidence).

AI assistance: Codex; tests verify independently calculated expected values.
"""

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from scripts.calculate_ci_metrics import GitHub, calculate, enrich_ancestry, run_times


def stamp(minute):
    return f"2026-11-01T{minute // 60:02d}:{minute % 60:02d}:00Z"


def run(
    sha="a",
    workflow=1,
    created=10,
    started=12,
    finished=20,
    conclusion="success",
    attempt=1,
    run_id=None,
):
    return {
        "id": run_id or workflow,
        "name": f"workflow-{workflow}",
        "workflow_id": workflow,
        "head_sha": sha,
        "head_branch": "main",
        "event": "push",
        "created_at": stamp(created),
        "updated_at": stamp(finished),
        "run_attempt": attempt,
        "status": "completed",
        "conclusion": conclusion,
        "html_url": "https://github.com/example/repo/actions/runs/1",
        "jobs": [
            {
                "name": "build",
                "started_at": stamp(started),
                "completed_at": stamp(finished),
                "status": "completed",
                "conclusion": conclusion,
            }
        ],
    }


def evidence(runs):
    return {
        "repository": "example/repo",
        "timezone": "UTC",
        "window_utc": {
            "from": "2026-11-01T00:00:00Z",
            "to_exclusive": "2026-11-15T00:00:00Z",
        },
        "workflows": ["workflow-1", "workflow-2"],
        "runs": runs,
        "changes": {
            r["head_sha"]: {"pr": {"number": 1}, "first_commit_at": stamp(0)}
            for r in runs
        },
        "ancestry": {},
    }


def test_parallel_workflows_are_one_deployment_and_wall_clock_is_not_summed():
    data = evidence([run(finished=20), run(workflow=2, started=15, finished=30)])
    result = calculate(data)
    assert result["deployment_frequency_per_week"] == 0.5
    assert result["counts"]["workflow_runs"] == 2
    assert result["lead_time_minutes"]["mean"] == 30
    row = result["records"][0]
    assert row["queue_minutes"] == 2
    assert row["execution_minutes"] == 18
    assert row["pre_ci_minutes"] == 10
    assert result["workflow_execution_minutes"]["median"] == 11.5
    assert sum(result["lead_time_parts"]["shares_percent"].values()) == pytest.approx(
        100
    )


def test_failed_attempt_is_preserved_after_successful_rerun():
    data = evidence(
        [run(conclusion="failure"), run(attempt=2, started=25, finished=30)]
    )
    result = calculate(data)
    assert result["counts"]["commits"] == 1
    assert result["counts"]["green_commits"] == 1
    assert result["change_failure_rate_percent"] == 100
    assert result["recovery_time_minutes"]["mean"] == 10
    assert result["records"][0]["status"] == "red_then_green"
    assert result["workflow_timings"][1]["queue_minutes"] is None


def test_failed_changes_receive_lead_time_from_first_green_descendant():
    data = evidence(
        [
            run(conclusion="failure"),
            run(sha="b", created=30, started=31, finished=40, run_id=2),
        ]
    )
    data["ancestry"]["a...b"] = "ahead"
    data["changes"]["b"]["first_commit_at"] = stamp(25)
    result = calculate(data)
    assert result["change_failure_rate_percent"] == 50
    assert result["lead_time_minutes"]["mean"] == 27.5
    assert result["recovery_time_minutes"]["median"] == 20
    assert result["records"][0]["deployed_by"] == "b"


def test_unrelated_green_does_not_supply_change_lead_time():
    data = evidence(
        [
            run(conclusion="failure"),
            run(sha="b", created=30, started=31, finished=40, run_id=2),
        ]
    )
    result = calculate(data)
    assert result["records"][0]["lead_minutes"] is None


def test_no_failure_is_not_zero_recovery():
    result = calculate(evidence([run()]))
    assert result["change_failure_rate_percent"] == 0
    assert result["recovery_time_minutes"]["mean"] is None
    assert result["recovery_time_minutes"]["count"] == 0


def test_unresolved_failure_is_reported_not_zero_filled():
    result = calculate(evidence([run(conclusion="failure")]))
    assert result["unresolved_failures"] == 1
    assert result["recovery_time_minutes"]["mean"] is None
    assert result["lead_time_minutes"]["count"] == 0


def test_cancelled_and_pending_are_not_successes_or_failures():
    cancelled = run(conclusion="cancelled")
    cancelled["jobs"] = []
    pending = run(sha="b", run_id=2)
    pending.update(status="queued", conclusion=None, jobs=[])
    result = calculate(evidence([cancelled, pending]))
    assert result["counts"]["completed_commits"] == 1
    assert result["counts"]["incomplete_commits"] == 1
    assert result["counts"]["green_commits"] == 0
    assert result["change_failure_rate_percent"] == 0
    assert result["records"][0]["queue_minutes"] is None
    assert result["warnings"]


def test_failure_in_one_of_several_workflows_makes_commit_red():
    result = calculate(evidence([run(), run(workflow=2, conclusion="failure")]))
    assert result["counts"]["green_commits"] == 0
    assert result["change_failure_rate_percent"] == 100


def test_pr_runs_are_excluded():
    pull_request = run(sha="b", conclusion="failure", run_id=2)
    pull_request["event"] = "pull_request"
    result = calculate(evidence([run(), pull_request]))
    assert result["counts"]["commits"] == 1
    assert result["change_failure_rate_percent"] == 0


def test_end_boundary_censors_future_successful_rerun():
    data = evidence(
        [run(conclusion="failure"), run(attempt=2, started=25, finished=30)]
    )
    data["window_utc"]["to_exclusive"] = stamp(30)
    result = calculate(data)
    assert result["counts"]["green_commits"] == 0
    assert result["unresolved_failures"] == 1


def test_empty_sample_is_undefined_failure_rate():
    result = calculate(evidence([]))
    assert result["deployment_frequency_per_week"] == 0
    assert result["change_failure_rate_percent"] is None


def test_run_end_uses_last_job_not_metadata_update():
    value = run()
    value["updated_at"] = stamp(45)
    value["jobs"].append(
        {
            "started_at": stamp(18),
            "completed_at": stamp(23),
            "status": "completed",
            "conclusion": "success",
        }
    )
    assert run_times(value)["completed_at"] == stamp(23)
    assert run_times(value)["execution_minutes"] == 11


def test_pagination_fetches_second_page(monkeypatch):
    api = GitHub("example/repo")
    calls = []

    def fake_get(endpoint, params):
        calls.append(params["page"])
        return {"jobs": list(range(100)) if params["page"] == 1 else [100]}

    monkeypatch.setattr(api, "get", fake_get)
    assert len(api.pages("/actions/runs/1/jobs", "jobs")) == 101
    assert calls == [1, 2]


def test_api_search_limit_is_not_silently_truncated(monkeypatch):
    api = GitHub("example/repo")
    monkeypatch.setattr(
        api, "get", lambda *args: {"total_count": 1001, "workflow_runs": []}
    )
    with pytest.raises(ValueError, match="1,000"):
        api.pages("/actions/runs", "workflow_runs")


def test_kyiv_window_converted_before_query():
    from zoneinfo import ZoneInfo

    start = datetime(2026, 11, 1, tzinfo=ZoneInfo("Europe/Kyiv")).astimezone(
        timezone.utc
    )
    assert start.isoformat() == "2026-10-31T22:00:00+00:00"


def test_direct_commit_uses_its_timestamp():
    data = evidence([run()])
    data["changes"]["a"]["pr"] = None
    data["changes"]["a"]["first_commit_at"] = stamp(9)
    result = calculate(data)
    assert result["records"][0]["pr"] is None
    assert result["lead_time_minutes"]["mean"] == 11


def test_input_is_not_modified():
    data = evidence([run()])
    original = deepcopy(data)
    calculate(data)
    assert data == original


def test_internal_idle_time_is_not_claimed_as_running_tests():
    data = evidence(
        [run(started=12, finished=15), run(workflow=2, started=35, finished=40)]
    )
    row = calculate(data)["records"][0]
    assert row["execution_minutes"] == 28
    assert row["active_job_minutes"] == 8
    assert row["internal_idle_minutes"] == 20


def test_later_failed_rerun_can_recover_without_counting_second_deployment():
    data = evidence(
        [
            run(),
            run(attempt=2, started=25, finished=30, conclusion="failure"),
            run(attempt=3, started=35, finished=40),
        ]
    )
    result = calculate(data)
    assert result["counts"]["green_commits"] == 1
    assert result["change_failure_rate_percent"] == 100
    assert result["recovery_time_minutes"]["mean"] == 10
    assert result["records"][0]["green_events"] == [stamp(20), stamp(40)]


def test_faster_green_descendant_deploys_change_before_its_own_slow_ci(monkeypatch):
    data = evidence(
        [run(finished=50), run(sha="b", created=25, started=26, finished=30, run_id=2)]
    )
    api = GitHub("example/repo")
    calls = []

    def compare(endpoint):
        calls.append(endpoint)
        return {"status": "ahead"}

    monkeypatch.setattr(api, "get", compare)
    enrich_ancestry(api, data)
    result = calculate(data)
    assert calls == ["/compare/a...b"]
    assert result["records"][0]["lead_minutes"] == 30
    assert result["records"][0]["execution_minutes"] == 38
    assert result["records"][0]["lead_execution_minutes"] == 18


def test_descendant_can_deploy_before_original_job_starts():
    data = evidence(
        [
            run(started=35, finished=50),
            run(sha="b", created=25, started=26, finished=30, run_id=2),
        ]
    )
    data["ancestry"]["a...b"] = "ahead"
    row = calculate(data)["records"][0]
    assert row["lead_minutes"] == 30
    assert row["lead_queue_minutes"] == 16
    assert row["lead_execution_minutes"] == 4
