"""Compare JUnit reports of repeated test runs and list tests whose result changed.

Lab 10 bonus «Пошук нестабільних тестів»: .github/workflows/lab10-flaky-tests.yml
runs the full test suite several times on one commit and puts the JUnit files
of each repeat into a separate directory, which this script then compares.

AI assistance: Claude Code (implementation and tests). Python 3.11+, standard library.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys

# The reports are produced by our own pytest/Vitest run in the same job,
# so they are trusted input.
import xml.etree.ElementTree as ET  # nosec B405

MIN_REPEATS = 5
MISSING = "missing"
# One repeat can list the same test twice (pytest records a teardown error
# as a second entry for an already passed test); the worst outcome wins.
SEVERITY = {"skipped": 0, "passed": 1, "failed": 2, "error": 3}
OUTCOME_LABELS = {
    "passed": "пройдено",
    "failed": "впав",
    "error": "помилка",
    "skipped": "пропущено",
    MISSING: "відсутній",
}


class ReportError(Exception):
    pass


def outcome(case: ET.Element) -> str:
    if case.find("error") is not None:
        return "error"
    if case.find("failure") is not None:
        return "failed"
    if case.find("skipped") is not None:
        return "skipped"
    return "passed"


def read_repeat(directory: Path) -> dict[str, str]:
    reports = sorted(directory.glob("*.xml"))
    if not reports:
        raise ReportError(f"{directory}: no JUnit XML reports")
    results: dict[str, str] = {}
    for report in reports:
        try:
            root = ET.parse(report).getroot()  # nosec B314
        except ET.ParseError as exc:
            raise ReportError(f"{report}: {exc}") from exc
        for case in root.iter("testcase"):
            test_id = f"{case.get('classname', '')}::{case.get('name', '')}"
            result = outcome(case)
            previous = results.get(test_id)
            if previous is None or SEVERITY[result] > SEVERITY[previous]:
                results[test_id] = result
    return results


def compare(
    repeats: list[dict[str, str]],
) -> tuple[list[str], dict[str, list[str]], list[str]]:
    """Return all test ids, tests with differing outcomes, tests failing every time."""
    test_ids = sorted(set().union(*repeats))
    flaky: dict[str, list[str]] = {}
    failing: list[str] = []
    for test_id in test_ids:
        outcomes = [repeat.get(test_id, MISSING) for repeat in repeats]
        if len(set(outcomes)) > 1:
            flaky[test_id] = outcomes
        elif outcomes[0] in ("failed", "error"):
            failing.append(test_id)
    return test_ids, flaky, failing


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def render(
    repeats: list[dict[str, str]],
    test_ids: list[str],
    flaky: dict[str, list[str]],
    failing: list[str],
) -> str:
    count = len(repeats)
    lines = [
        "## Пошук нестабільних тестів",
        "",
        f"Повторів на одному коміті: **{count}**, унікальних тестів: **{len(test_ids)}**.",
        "",
        "| Повтор | Тестів | Пройдено | Впали | Помилки | Пропущено |",
        "|---|---|---|---|---|---|",
    ]
    for number, repeat in enumerate(repeats, start=1):
        totals = Counter(repeat.values())
        lines.append(
            f"| {number} | {len(repeat)} | {totals['passed']} | {totals['failed']} "
            f"| {totals['error']} | {totals['skipped']} |"
        )

    lines += ["", f"### Результат відрізнявся між повторами: {len(flaky)}", ""]
    if flaky:
        header = " | ".join(str(number) for number in range(1, count + 1))
        lines += [f"| Тест | {header} |", "|---" * (count + 1) + "|"]
        for test_id, outcomes in flaky.items():
            cells = " | ".join(OUTCOME_LABELS[item] for item in outcomes)
            lines.append(f"| `{_cell(test_id)}` | {cells} |")
    else:
        lines.append(
            f"Не знайдено: кожен тест мав однаковий результат у всіх {count} повторах."
        )

    lines += ["", f"### Падають у кожному повторі: {len(failing)}", ""]
    if failing:
        lines += [f"- `{test_id}`" for test_id in failing]
    else:
        lines.append("Немає.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="List tests whose result differed between repeated runs."
    )
    parser.add_argument(
        "repeats",
        nargs="+",
        type=Path,
        help="one directory of JUnit XML files per repeat, in run order",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        help="also append the Markdown report to this file, e.g. $GITHUB_STEP_SUMMARY",
    )
    args = parser.parse_args(argv)
    if len(args.repeats) < MIN_REPEATS:
        parser.error(f"need at least {MIN_REPEATS} repeats, got {len(args.repeats)}")

    try:
        repeats = [read_repeat(directory) for directory in args.repeats]
    except ReportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    test_ids, flaky, failing = compare(repeats)
    if not test_ids:
        print("error: the reports contain no test cases", file=sys.stderr)
        return 2

    report = render(repeats, test_ids, flaky, failing)
    print(report)
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as summary:
            summary.write(report + "\n")
    return 1 if flaky or failing else 0


if __name__ == "__main__":
    sys.exit(main())
