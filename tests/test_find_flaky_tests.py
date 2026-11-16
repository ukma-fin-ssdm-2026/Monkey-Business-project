"""Lab 10 bonus «Пошук нестабільних тестів»: comparison of repeated JUnit reports.

Synthetic XML only; the expected outcomes for each case are written by hand.
AI assistance: Claude Code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.find_flaky_tests import compare, main, read_repeat

CHILD = {
    "passed": "",
    "failed": '<failure message="assert False"/>',
    "error": '<error message="fixture failed"/>',
    "skipped": '<skipped message="no database"/>',
}


def write_report(path: Path, cases: list[tuple[str, str]]) -> None:
    body = "".join(
        f'<testcase classname="tests.test_x" name="{name}">{CHILD[result]}</testcase>'
        for name, result in cases
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<?xml version="1.0"?><testsuites><testsuite name="pytest">{body}'
        "</testsuite></testsuites>",
        encoding="utf-8",
    )


def make_repeats(tmp_path: Path, repeats: list[dict[str, str]]) -> list[Path]:
    directories = []
    for number, cases in enumerate(repeats, start=1):
        directory = tmp_path / f"run-{number:02d}"
        write_report(directory / "backend.xml", list(cases.items()))
        directories.append(directory)
    return directories


def as_args(directories: list[Path]) -> list[str]:
    return [str(directory) for directory in directories]


def test_stable_suite_has_no_flaky_tests(tmp_path, capsys):
    stable = {"test_a": "passed", "test_db": "skipped"}
    directories = make_repeats(tmp_path, [stable] * 5)

    assert main(as_args(directories)) == 0
    assert "Не знайдено" in capsys.readouterr().out


def test_failure_in_one_repeat_is_reported_with_every_outcome(tmp_path):
    repeats = [{"test_a": "passed", "test_b": "passed"} for _ in range(5)]
    repeats[2]["test_b"] = "failed"
    directories = make_repeats(tmp_path, repeats)

    _, flaky, failing = compare([read_repeat(d) for d in directories])

    assert flaky == {
        "tests.test_x::test_b": ["passed", "passed", "failed", "passed", "passed"]
    }
    assert failing == []
    assert main(as_args(directories)) == 1


def test_test_failing_in_every_repeat_is_not_flaky(tmp_path):
    directories = make_repeats(tmp_path, [{"test_a": "failed"}] * 5)

    _, flaky, failing = compare([read_repeat(d) for d in directories])

    assert flaky == {}
    assert failing == ["tests.test_x::test_a"]
    assert main(as_args(directories)) == 1


def test_test_missing_from_one_repeat_counts_as_different(tmp_path):
    repeats = [{"test_a": "passed", "test_b": "passed"} for _ in range(5)]
    del repeats[1]["test_b"]
    directories = make_repeats(tmp_path, repeats)

    _, flaky, _ = compare([read_repeat(d) for d in directories])

    assert flaky["tests.test_x::test_b"][1] == "missing"


def test_reports_of_one_repeat_are_merged(tmp_path):
    directory = tmp_path / "run-01"
    write_report(directory / "backend.xml", [("test_api", "passed")])
    write_report(directory / "frontend.xml", [("renders page", "failed")])

    assert read_repeat(directory) == {
        "tests.test_x::test_api": "passed",
        "tests.test_x::renders page": "failed",
    }


def test_duplicate_entry_keeps_the_worst_outcome(tmp_path):
    report = tmp_path / "run-01" / "backend.xml"
    write_report(report, [("test_a", "passed"), ("test_a", "error")])

    assert read_repeat(report.parent) == {"tests.test_x::test_a": "error"}


def test_fewer_than_five_repeats_are_rejected(tmp_path):
    directories = make_repeats(tmp_path, [{"test_a": "passed"}] * 4)

    with pytest.raises(SystemExit) as exit_info:
        main(as_args(directories))

    assert exit_info.value.code == 2


def test_repeat_without_reports_is_an_error(tmp_path, capsys):
    directories = make_repeats(tmp_path, [{"test_a": "passed"}] * 4)
    empty = tmp_path / "run-05"
    empty.mkdir()

    assert main(as_args(directories + [empty])) == 2
    assert "no JUnit XML reports" in capsys.readouterr().err


def test_report_is_appended_to_summary_file(tmp_path):
    directories = make_repeats(tmp_path, [{"test_a": "passed"}] * 5)
    summary = tmp_path / "summary.md"
    summary.write_text("### Earlier step\n", encoding="utf-8")

    main(as_args(directories) + ["--summary", str(summary)])

    text = summary.read_text(encoding="utf-8")
    assert text.startswith("### Earlier step\n")
    assert "## Пошук нестабільних тестів" in text
