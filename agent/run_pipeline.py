#!/usr/bin/env python3
"""Run the Playwright suite, analyze failures, and for each failure both:

  - append it to reports/report.md (local reporting, unchanged), and
  - file a GitHub issue + "Testing log" project entry (new).

This is a thin orchestrator over run_and_analyze.py (test running, JSON
parsing, rule-based analysis, local markdown report) and
create_testing_log.py (GitHub issue + project logic) -- neither of those
modules is modified; this script just wires them together per failure.
"""

import sys
from pathlib import Path

# Both sibling modules live in this same agent/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_and_analyze import (
    REPO_ROOT,
    REPORT_PATH,
    run_playwright_tests,
    flatten_tests,
    analyze_failure,
    find_screenshot,
    write_markdown_report,
)
from create_testing_log import create_testing_log


def main():
    report = run_playwright_tests()
    tests = flatten_tests(report)

    total = len(tests)
    passed = sum(1 for t in tests if t["status"] == "passed")
    skipped = sum(1 for t in tests if t["status"] == "skipped")
    failed = total - passed - skipped

    failures = []
    for t in tests:
        if t["status"] in ("passed", "skipped"):
            continue

        analysis = analyze_failure(t["error_message"], t["stack_trace"])
        screenshot_rel = find_screenshot(t["title"], t["project"], t["screenshot_path"])
        failures.append({**t, **analysis, "screenshot": screenshot_rel})

        # create_testing_log needs a real on-disk file to copy, not just the
        # repo-relative link used in the markdown report -- prefer the
        # original absolute attachment path Playwright recorded, and fall
        # back to resolving the fuzzy-matched relative path against the repo
        # root if that's all we have.
        screenshot_abs = t["screenshot_path"] or (
            str(REPO_ROOT / screenshot_rel) if screenshot_rel else None
        )

        if screenshot_abs:
            create_testing_log(
                t["title"],
                t["project"],
                t["error_message"] or "(no error message captured)",
                screenshot_abs,
            )
        else:
            print(
                f"[run_pipeline] No screenshot found for '{t['title']}' "
                f"({t['project']}) -- skipping GitHub logging for this failure."
            )

    write_markdown_report(total, passed, failed, skipped, failures)

    report_rel_path = REPORT_PATH.relative_to(REPO_ROOT).as_posix()
    print(
        f"{total} tests run, {passed} passed, {failed} failed. "
        f"Report written to {report_rel_path}"
    )


if __name__ == "__main__":
    main()
