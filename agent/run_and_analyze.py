#!/usr/bin/env python3
"""Run the Playwright suite, parse the JSON results, and generate a
rule-based failure-analysis report.

Usage:
    python agent/run_and_analyze.py

Run from anywhere -- paths are resolved relative to this file's location
(the dummy-testing-agent repo root is this file's parent directory).
"""

import difflib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# --- Paths -------------------------------------------------------------
# agent/run_and_analyze.py -> repo root is one directory up.
REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_RESULTS_DIR = REPO_ROOT / "test-results"
REPORTS_DIR = REPO_ROOT / "reports"
REPORT_PATH = REPORTS_DIR / "report.md"

# Playwright colorizes call-log output with ANSI escape codes even in JSON
# reporter output; strip them so error text is clean for matching and display.
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text):
    return _ANSI_ESCAPE_RE.sub("", text) if text else text


def run_playwright_tests():
    """Run `npx playwright test --reporter=json` and return the parsed report.

    Playwright's JSON reporter prints the full report as a single JSON blob
    to stdout when invoked via --reporter=json (no output file needed), so
    we just capture stdout and json.loads() it. shell=True lets this resolve
    `npx` correctly on Windows (where it's `npx.cmd`), and works the same way
    on other platforms.
    """
    result = subprocess.run(
        "npx playwright test --reporter=json",
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        shell=True,
    )

    # Playwright exits non-zero when tests fail -- that's expected and not
    # itself an error condition here. Only bail if there's no JSON to parse.
    if not result.stdout.strip():
        print("Playwright produced no stdout output to parse.", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(f"Failed to parse Playwright JSON output: {exc}", file=sys.stderr)
        print(result.stdout[:2000], file=sys.stderr)
        sys.exit(1)


def flatten_tests(report):
    """Flatten Playwright's nested suites/specs/tests/results structure.

    The JSON report nests suites inside suites (one level per describe
    block plus one for the file itself), each holding `specs`, each spec
    holding one `test` entry per project (browser), each test holding a
    `results` list (multiple entries only if retries ran).

    Each result carries both a singular `error` (often just a generic
    "Test timeout exceeded" summary) and a plural `errors` list, which
    usually includes a second, more specific entry with the actual
    Playwright call log (e.g. "waiting for getByTestId(...)"). We use the
    last (most specific) entry in `errors` for analysis/display, falling
    back to `error` if `errors` is empty. `attachments` gives us the exact
    on-disk screenshot path when Playwright saved one.

    Returns a flat list of dicts: title, project, status, error_message,
    stack_trace, screenshot_path (absolute path string or None).
    """
    flattened = []

    def walk_suites(suites):
        for suite in suites:
            for spec in suite.get("specs", []):
                title = spec.get("title", "<unknown>")
                for test in spec.get("tests", []):
                    project = test.get("projectName", "<unknown>")
                    results = test.get("results", [])
                    # Last result reflects the final outcome after any retries.
                    final_result = results[-1] if results else {}
                    status = final_result.get("status", "unknown")

                    errors = final_result.get("errors") or []
                    best_error = errors[-1] if errors else (final_result.get("error") or {})

                    screenshot_path = None
                    for attachment in final_result.get("attachments", []):
                        if attachment.get("name") == "screenshot":
                            screenshot_path = attachment.get("path")
                            break

                    flattened.append(
                        {
                            "title": title,
                            "project": project,
                            "status": status,
                            "error_message": _strip_ansi(best_error.get("message")),
                            "stack_trace": _strip_ansi(best_error.get("stack")),
                            "screenshot_path": screenshot_path,
                        }
                    )
            # Suites can nest (describe blocks) -- recurse.
            walk_suites(suite.get("suites", []))

    walk_suites(report.get("suites", []))
    return flattened


def _slug(text):
    """Lowercase, alphanumeric-only form of `text`, for fuzzy folder matching."""
    return "".join(ch.lower() for ch in text if ch.isalnum())


def find_screenshot(test_title, project, screenshot_path=None):
    """Locate the screenshot Playwright saved for a failed test.

    Prefer the exact path Playwright already recorded in the result's
    `attachments` array (screenshot_path) -- that's the authoritative
    source once `screenshot: 'only-on-failure'` is set in the config. Only
    fall back to a fuzzy search of test-results/ (by folder name) if no
    attachment path was available, e.g. for older result data.

    Playwright names each test's output folder from the spec file name,
    suite titles, and test title (sanitized into dashes) plus the project
    name, e.g. `auth-Dummy-App-Auth-Flow-Invalid-Login-chromium`. Rather
    than reimplement that exact sanitization for the fallback path, we
    fuzzy-match: the folder name must contain the project name, and its
    similarity to the test title is scored with difflib.

    Returns a repo-relative path string, or None if nothing was found.
    """
    if screenshot_path:
        resolved = Path(screenshot_path)
        if resolved.is_file():
            try:
                return resolved.relative_to(REPO_ROOT).as_posix()
            except ValueError:
                # Not under REPO_ROOT for some reason -- fall through to search.
                pass

    if not TEST_RESULTS_DIR.is_dir():
        return None

    title_slug = _slug(test_title)
    project_slug = _slug(project)

    best_dir = None
    best_score = 0.0

    for entry in TEST_RESULTS_DIR.iterdir():
        if not entry.is_dir():
            continue
        dir_slug = _slug(entry.name)
        if project_slug and project_slug not in dir_slug:
            continue
        score = difflib.SequenceMatcher(None, title_slug, dir_slug).ratio()
        if score > best_score:
            best_score = score
            best_dir = entry

    if best_dir is None or best_score < 0.3:
        return None

    # Playwright's usual screenshot filenames for a failure.
    for candidate in ("test-failed-1.png", "test-failed-2.png"):
        screenshot = best_dir / candidate
        if screenshot.is_file():
            return screenshot.relative_to(REPO_ROOT).as_posix()

    # Fall back to any PNG in the folder.
    for png in best_dir.glob("*.png"):
        return png.relative_to(REPO_ROOT).as_posix()

    return None


def analyze_failure(error_message, stack_trace):
    """Rule-based root-cause analysis for a single failed test.

    Pattern-matches the error message and stack trace against a few common
    Playwright failure signatures and returns a dict with root_cause,
    severity, confidence (0-100), and suggested_fix. Anything that doesn't
    match a known pattern falls into a generic low-confidence bucket --
    this is a simple heuristic classifier, not exhaustive log analysis.
    """
    text = f"{error_message or ''}\n{stack_trace or ''}"

    # Playwright's call log for an element-wait timeout reads "waiting for
    # locator(...)", "waiting for getByTestId(...)", "waiting for
    # getByRole(...)", etc. -- match the family, not just the literal
    # "locator"/"selector" wording. Case-insensitive since Playwright's own
    # messages use a lowercase "Test timeout of ...".
    has_timeout = "timeout" in text.lower()
    waiting_for_element = bool(re.search(r"waiting for (locator|selector|getBy\w+)", text, re.IGNORECASE))

    if has_timeout and waiting_for_element:
        return {
            "root_cause": (
                "Likely a selector/data-testid mismatch, or the element never "
                "rendered in time (app crash, slow network, wrong route, etc.)."
            ),
            "severity": "high",
            "confidence": 75,
            "suggested_fix": (
                "Check whether the element's data-testid or selector changed in "
                "the app code, and confirm the page actually reaches the expected "
                "state before the timeout elapses."
            ),
        }

    if "net::ERR" in text or "ECONNREFUSED" in text:
        return {
            "root_cause": "The application/server was not reachable during the test run.",
            "severity": "critical",
            "confidence": 90,
            "suggested_fix": (
                "Verify the dev server is running and that playwright.config.js's "
                "baseURL points at the correct host and port."
            ),
        }

    return {
        "root_cause": "Unclassified failure - manual review needed.",
        "severity": "medium",
        "confidence": 20,
        "suggested_fix": "Review the full error message and stack trace manually.",
    }


def write_markdown_report(total, passed, failed, skipped, failures):
    """Write the markdown summary + per-failure detail report to reports/report.md."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Playwright Test Report",
        "",
        f"- **Timestamp:** {datetime.now(timezone.utc).isoformat()}",
        f"- **Total tests:** {total}",
        f"- **Passed:** {passed}",
        f"- **Failed:** {failed}",
    ]
    if skipped:
        lines.append(f"- **Skipped:** {skipped}")
    lines.append("")

    if not failures:
        lines.append("All tests passed. No failures to report.")
    else:
        lines.append("## Failures")
        lines.append("")
        for i, f in enumerate(failures, start=1):
            error_message = f["error_message"] or "(no error message captured)"
            if len(error_message) > 500:
                error_message = error_message[:500] + "... (truncated)"

            lines.append(f"### {i}. {f['title']} ({f['project']})")
            lines.append("")
            lines.append(f"- **Error:** {error_message}")
            lines.append(f"- **Root cause:** {f['root_cause']}")
            lines.append(f"- **Severity:** {f['severity']}")
            lines.append(f"- **Confidence:** {f['confidence']}%")
            lines.append(f"- **Suggested fix:** {f['suggested_fix']}")
            if f["screenshot"]:
                lines.append(f"- **Screenshot:** [{f['screenshot']}]({f['screenshot']})")
            else:
                lines.append("- **Screenshot:** no screenshot found")
            lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


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
        screenshot = find_screenshot(t["title"], t["project"], t["screenshot_path"])
        failures.append({**t, **analysis, "screenshot": screenshot})

    write_markdown_report(total, passed, failed, skipped, failures)

    report_rel_path = REPORT_PATH.relative_to(REPO_ROOT).as_posix()
    print(
        f"{total} tests run, {passed} passed, {failed} failed. "
        f"Report written to {report_rel_path}"
    )


if __name__ == "__main__":
    main()
