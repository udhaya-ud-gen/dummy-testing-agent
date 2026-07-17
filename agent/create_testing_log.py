#!/usr/bin/env python3
"""Turn a single Playwright test failure into a permanent GitHub record.

Given a failing test's name, browser, error message, and a screenshot file,
this module:

  1. Copies the screenshot into evidence/ in *this* repo (dummy-testing-agent),
     commits it, and pushes it to the current branch -- so it gets a
     permanent raw.githubusercontent.com URL. The destination filename is
     unique per (test name, browser, commit) so that two different failing
     tests in the same run never collide and overwrite each other's
     evidence file.
  2. Checks whether a real GitHub Issue for this exact test+browser already
     exists on udhaya-ud-gen/dummy-app (by exact title-suffix match via the
     REST issues list -- see find_existing_issue for why it's a suffix
     match, not a full-title match). If so, it's a re-occurrence: post a
     structured comment with the new screenshot on the existing issue
     instead of creating a new one. If not, create a new Issue with a
     structured, human-readable body (Issue Description / Expected /
     Actual / Possible Reasons / Error Detail / Screenshot), a label that
     says whether this run was automated (CI) or local, add it to
     udhaya-ud-gen's GitHub Project (number 1), and set its Status field to
     "Testing log".

We're on real repo Issues here (not Projects v2 Draft Issues) -- these
need to show up in udhaya-ud-gen/dummy-app's own Issues tab, so a real
issue (with REST-visible comments, issue number, etc.) is the right fit.
That means duplicate detection and re-occurrence notes both go through the
REST API (issues list + issue comments) rather than GraphQL, while adding
the issue to the project board and setting its Status still needs GraphQL
(Projects v2 has no REST equivalent for that).

Requires the GH_PAT environment variable: a GitHub personal access token
with repo (issues + contents) and project scopes.

Usage (standalone CLI):
    python agent/create_testing_log.py "Valid Login" chromium "Timeout ..." /path/to/screenshot.png

Usage (as a library, e.g. from run_pipeline.py):
    from create_testing_log import create_testing_log
    create_testing_log(test_name, browser, error_message, screenshot_path, stack_trace)
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

# Reuse the existing rule-based classifier instead of duplicating it --
# both scripts live in this same agent/ directory, so this resolves whether
# create_testing_log.py is run standalone (Python auto-adds its own
# directory to sys.path) or imported by run_pipeline.py (which inserts the
# agent/ directory into sys.path before importing either module).
from run_and_analyze import analyze_failure

# --- Configuration -------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = REPO_ROOT / "evidence"

ISSUE_OWNER = "udhaya-ud-gen"
ISSUE_REPO = "dummy-app"          # repo the failure issue gets filed in

PROJECT_OWNER = "udhaya-ud-gen"   # user who owns the GitHub Project
PROJECT_NUMBER = 1
STATUS_FIELD_NAME = "Status"
STATUS_OPTION_NAME = "Testing log"

# Every issue this script creates carries a "[Test Failure] <test> (<browser>)"
# suffix in the title (see _build_issue_title). find_existing_issue matches
# on that suffix so a re-run's cleaner, category-prefixed title still finds
# the original issue instead of filing a duplicate.
TITLE_TAG_TEMPLATE = "[Test Failure] {test_name} ({browser})"

LABEL_AUTOMATED = "Bug : Automated test"
LABEL_LOCAL = "Bug : Local test"

GITHUB_API = "https://api.github.com"
GITHUB_GRAPHQL_API = "https://api.github.com/graphql"


def _get_pat():
    """Read the GitHub PAT from the environment. Fatal if missing -- nothing
    in this module works without it."""
    pat = os.environ.get("GH_PAT")
    if not pat:
        print("[create_testing_log] ERROR: GH_PAT environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    return pat


def _slug(text):
    """Lowercase, dash-separated, alphanumeric-only form of `text`, safe to
    use inside a filename (e.g. 'Valid Login' -> 'valid-login')."""
    out = []
    prev_dash = False
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    return "".join(out).strip("-")


def _is_ci_run():
    """True when this is running inside GitHub Actions. GitHub Actions sets
    the CI and GITHUB_ACTIONS environment variables automatically on every
    hosted/self-hosted runner, so this needs no extra configuration."""
    return os.environ.get("GITHUB_ACTIONS", "").lower() == "true"


def _get_label_for_run():
    """Which label this run's issues/comments should be tagged with --
    distinguishes CI-triggered failures from ones logged while testing
    locally, so the two never get confused in the Issues list."""
    return LABEL_AUTOMATED if _is_ci_run() else LABEL_LOCAL


def _run_git(*args):
    """Run a git command in this repo's root; return (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _get_current_branch():
    code, out, err = _run_git("rev-parse", "--abbrev-ref", "HEAD")
    if code != 0:
        raise RuntimeError(f"Could not determine current git branch: {err}")
    return out


def _get_short_sha():
    """Short hash of the current HEAD, or 'unknown' if it can't be read."""
    code, out, _ = _run_git("rev-parse", "--short", "HEAD")
    return out if code == 0 and out else "unknown"


def _get_origin_owner_repo():
    """Parse the `origin` remote URL into (owner, repo), for building the
    raw.githubusercontent.com URL. Handles both HTTPS and SSH remote forms."""
    code, out, err = _run_git("remote", "get-url", "origin")
    if code != 0:
        raise RuntimeError(f"Could not read origin remote URL: {err}")

    url = out
    if url.startswith("git@github.com:"):
        path = url[len("git@github.com:"):]
    elif "github.com/" in url:
        path = url.split("github.com/", 1)[1]
    else:
        raise RuntimeError(f"Unrecognized origin remote URL: {url}")

    path = path[:-len(".git")] if path.endswith(".git") else path
    owner, repo = path.split("/", 1)
    return owner, repo


def push_screenshot(screenshot_path, pat, test_name, browser):
    """Copy the screenshot into evidence/, commit it, and push to the
    current branch using the PAT for auth. Returns the resulting
    raw.githubusercontent.com URL.

    The destination filename is built from the test name + browser + short
    commit SHA -- not just the source filename's stem. Playwright names
    every failure screenshot "test-failed-1.png" inside that test's own
    results folder, so using only the stem (as a previous version of this
    function did) made every failing test in the same run collide onto the
    exact same evidence/ filename, silently overwriting each other. Adding
    the test name and browser makes each destination name unique per test,
    even when several tests fail in the same run/commit.
    """
    screenshot_path = Path(screenshot_path)
    if not screenshot_path.is_file():
        raise FileNotFoundError(f"Screenshot not found: {screenshot_path}")

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    unique_id = f"{_slug(test_name)}-{_slug(browser)}-{_get_short_sha()}"
    dest_name = f"{unique_id}{screenshot_path.suffix}"
    dest_path = EVIDENCE_DIR / dest_name
    shutil.copyfile(screenshot_path, dest_path)
    rel_path = dest_path.relative_to(REPO_ROOT).as_posix()
    print(f"[create_testing_log] Copied screenshot to {rel_path}")

    code, out, err = _run_git("add", rel_path)
    if code != 0:
        raise RuntimeError(f"git add failed: {err}")

    code, out, err = _run_git("commit", "-m", f"Add test failure evidence: {dest_name}")
    if code != 0:
        raise RuntimeError(f"git commit failed: {err}")
    print("[create_testing_log] Committed evidence screenshot.")

    branch = _get_current_branch()
    owner, repo = _get_origin_owner_repo()
    # Embed the PAT in the push URL for this one push only -- this does not
    # touch the configured `origin` remote or persist credentials anywhere.
    push_url = f"https://x-access-token:{pat}@github.com/{owner}/{repo}.git"

    code, out, err = _run_git("push", push_url, f"HEAD:{branch}")
    if code != 0:
        raise RuntimeError(f"git push failed: {err}")
    print(f"[create_testing_log] Pushed evidence to branch '{branch}'.")

    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{rel_path}"
    return raw_url


def find_existing_issue(title_tag, pat):
    """Check ISSUE_OWNER/ISSUE_REPO for an already-filed issue whose title
    ends with this exact "[Test Failure] <test> (<browser>)" tag (state=all,
    so a closed one still counts as "already logged").

    Matching on the tag suffix -- not the full title -- means the
    human-readable, root-cause-based prefix (e.g. "[Network] ...") can
    change between runs without breaking duplicate detection, since the
    tag itself is still deterministic per test+browser.

    Returns the matching issue's REST JSON (has 'number', 'node_id',
    'html_url', etc.), or None if this test hasn't failed before.
    """
    response = requests.get(
        f"{GITHUB_API}/repos/{ISSUE_OWNER}/{ISSUE_REPO}/issues",
        params={"state": "all", "per_page": 100},
        headers={
            "Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"Failed to list issues ({response.status_code}): {response.text}")

    for issue in response.json():
        # The issues-list endpoint also returns pull requests; skip those.
        if "pull_request" in issue:
            continue
        if issue.get("title", "").endswith(title_tag):
            return issue
    return None


def create_issue(title, body, label, pat):
    """Create a new GitHub Issue on ISSUE_OWNER/ISSUE_REPO. GitHub creates
    the label automatically (with a default color) if it doesn't already
    exist on the repo, so no separate "ensure label exists" step is needed.
    Returns the parsed JSON response (contains 'html_url', 'node_id',
    'number', etc.)."""
    response = requests.post(
        f"{GITHUB_API}/repos/{ISSUE_OWNER}/{ISSUE_REPO}/issues",
        json={"title": title, "body": body, "labels": [label]},
        headers={
            "Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"Failed to create issue ({response.status_code}): {response.text}")

    data = response.json()
    print(f"[create_testing_log] Created issue #{data['number']}: {data['html_url']}")
    return data


def add_comment_to_issue(issue_number, body, pat):
    """Post a comment on an existing issue -- used for the re-occurrence
    note instead of filing a duplicate issue for the same test."""
    response = requests.post(
        f"{GITHUB_API}/repos/{ISSUE_OWNER}/{ISSUE_REPO}/issues/{issue_number}/comments",
        json={"body": body},
        headers={
            "Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"Failed to comment on issue #{issue_number} ({response.status_code}): {response.text}")
    print(f"[create_testing_log] Commented on existing issue #{issue_number}.")


def add_label_to_issue(issue_number, label, pat):
    """Make sure the current run's label (automated/local) is present on an
    existing issue too, even if it was originally filed under the other
    label -- e.g. a bug first caught locally that later reproduces in CI."""
    response = requests.post(
        f"{GITHUB_API}/repos/{ISSUE_OWNER}/{ISSUE_REPO}/issues/{issue_number}/labels",
        json={"labels": [label]},
        headers={
            "Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"Failed to add label to issue #{issue_number} ({response.status_code}): {response.text}")


def _graphql(query, variables, pat):
    """Run a single GraphQL query/mutation against the GitHub API.

    Only the "add to project" + "set Status field" steps use GraphQL --
    Projects v2 has no REST equivalent for either. Everything issue-related
    (list/create/comment/label) goes through the REST helpers above.
    """
    response = requests.post(
        GITHUB_GRAPHQL_API,
        json={"query": query, "variables": variables},
        headers={
            "Authorization": f"Bearer {pat}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"GraphQL request failed ({response.status_code}): {response.text}")

    data = response.json()
    if data.get("errors"):
        raise RuntimeError(f"GraphQL returned errors: {data['errors']}")
    return data["data"]


def get_project_status_field(pat):
    """Look up the project's node ID, the 'Status' field's node ID, and the
    'Testing log' option ID for PROJECT_OWNER's project PROJECT_NUMBER."""
    query = """
    query($login: String!, $number: Int!) {
      user(login: $login) {
        projectV2(number: $number) {
          id
          fields(first: 20) {
            nodes {
              ... on ProjectV2SingleSelectField {
                id
                name
                options {
                  id
                  name
                }
              }
            }
          }
        }
      }
    }
    """
    data = _graphql(query, {"login": PROJECT_OWNER, "number": PROJECT_NUMBER}, pat)
    project = data["user"]["projectV2"]
    if project is None:
        raise RuntimeError(f"Project number {PROJECT_NUMBER} not found for user {PROJECT_OWNER}.")
    project_id = project["id"]

    status_field = next(
        (f for f in project["fields"]["nodes"] if f and f.get("name") == STATUS_FIELD_NAME),
        None,
    )
    if status_field is None:
        raise RuntimeError(f"'{STATUS_FIELD_NAME}' field not found on the project.")

    status_option = next(
        (o for o in status_field["options"] if o["name"] == STATUS_OPTION_NAME),
        None,
    )
    if status_option is None:
        raise RuntimeError(f"'{STATUS_OPTION_NAME}' option not found on the '{STATUS_FIELD_NAME}' field.")

    return project_id, status_field["id"], status_option["id"]


def add_issue_to_project(issue_node_id, project_id, pat):
    """Add the issue (by its GraphQL node ID) to the project. Returns the
    project item's ID, needed to set its field values."""
    mutation = """
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
        item {
          id
        }
      }
    }
    """
    data = _graphql(mutation, {"projectId": project_id, "contentId": issue_node_id}, pat)
    return data["addProjectV2ItemById"]["item"]["id"]


def set_status_field(project_id, item_id, field_id, option_id, pat):
    """Set the project item's single-select Status field to the given option."""
    mutation = """
    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
      updateProjectV2ItemFieldValue(input: {
        projectId: $projectId,
        itemId: $itemId,
        fieldId: $fieldId,
        value: { singleSelectOptionId: $optionId }
      }) {
        projectV2Item {
          id
        }
      }
    }
    """
    _graphql(
        mutation,
        {"projectId": project_id, "itemId": item_id, "fieldId": field_id, "optionId": option_id},
        pat,
    )


def _truncate(text, limit=1200):
    text = text or "(no error message captured)"
    if len(text) > limit:
        return text[:limit] + "... (truncated)"
    return text


def _first_line(text, fallback):
    """The first non-empty line of `text`, used as a short "Actual Result"
    summary -- Playwright's error messages put the concise summary on line
    one and the full call log/stack on the lines after it."""
    if not text:
        return fallback
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return fallback


def _build_issue_title(test_name, browser, analysis):
    """Build a title that tells you what's actually wrong at a glance,
    instead of just repeating the test name. The "[Test Failure] <test>
    (<browser>)" tag is still appended at the end (see TITLE_TAG_TEMPLATE)
    so find_existing_issue's suffix match keeps working across runs even
    if the human-readable prefix text changes.
    """
    tag = TITLE_TAG_TEMPLATE.format(test_name=test_name, browser=browser)
    category = analysis["category"]

    if category == "Network":
        prefix = "App server unreachable"
    elif category == "UI":
        prefix = "Expected element not found / timed out"
    else:
        prefix = "Unclassified failure"

    return f"[{category}] {prefix} - {tag}"


def _build_new_issue_body(test_name, browser, error_message, stack_trace, screenshot_url, analysis):
    """Compose the structured body for a brand-new issue. Every section is
    grounded in real data (the actual error/stack trace and the rule-based
    analysis) rather than being a generic filler paragraph:

      - Issue Description   : what test failed, on which browser, in one line.
      - Expected Result      : what should have happened (from analysis).
      - Actual Result         : the concise, one-line version of the real error.
      - Possible Reasons for Failure : root cause + suggested fix (from analysis).
      - Error Detail          : the full raw error + stack trace, verbatim.
      - Screenshot            : the page as it looked at the moment of failure.
    """
    actual_result = _first_line(error_message, "(no error message captured)")

    return (
        f"### Issue Description\n"
        f"The **{test_name}** test failed on **{browser}**.\n\n"
        f"### What Steps Should Have Been Done (Expected)\n"
        f"Run the **{test_name}** test flow to completion on **{browser}** "
        f"without errors.\n\n"
        f"### Expected Result\n"
        f"{analysis['expected_result']}\n\n"
        f"### What Steps Were Actually Done (Actual)\n"
        f"The test executed the same flow, but failed at the point described "
        f"below instead of completing normally.\n\n"
        f"### Possible Reasons for Failure\n"
        f"{analysis['root_cause']} "
        f"(Severity: {analysis['severity']}, Confidence: {analysis['confidence']}%)\n\n"
        f"**Suggested fix:** {analysis['suggested_fix']}\n\n"
        f"### Actual Result\n"
        f"{actual_result}\n\n"
        f"### Error Detail\n"
        f"```\n{_truncate(error_message)}\n```\n\n"
        f"### Screenshot\n"
        f"![screenshot]({screenshot_url})\n"
    )


def _build_reoccurrence_comment(error_message, screenshot_url):
    """Compose the comment body posted on an existing issue when the same
    test fails again. Includes the fresh error text (not just "same error
    reproduced") plus the new screenshot, so each re-occurrence is
    self-explanatory without having to scroll back to the original issue
    body.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    commit = _get_short_sha()
    actual_result = _first_line(error_message, "(no error message captured)")

    return (
        f"### Re-occurred\n"
        f"**Time:** {timestamp}\n"
        f"**Commit:** {commit}\n\n"
        f"### Actual Result\n"
        f"{actual_result}\n\n"
        f"### Error Detail\n"
        f"```\n{_truncate(error_message)}\n```\n\n"
        f"### Screenshot\n"
        f"![screenshot]({screenshot_url})\n"
    )


def create_testing_log(test_name, browser, error_message, screenshot_path, stack_trace=None):
    """End-to-end: push screenshot evidence, then either create a new
    Issue for this failure or comment on an existing one if this exact
    test already has an open/closed issue on file.

    Each stage prints a clear success/error message. A failure in a later
    stage does not undo earlier stages -- e.g. if the screenshot push
    succeeds but the project API call then fails, the screenshot commit
    and the issue that was already created both stay. This keeps a batch
    caller (run_pipeline.py) able to move on to the next failing test.

    Returns the issue's HTML URL on success, or None if the failure
    couldn't be logged at all.
    """
    pat = _get_pat()
    analysis = analyze_failure(error_message, stack_trace)
    label = _get_label_for_run()
    title_tag = TITLE_TAG_TEMPLATE.format(test_name=test_name, browser=browser)
    title = _build_issue_title(test_name, browser, analysis)

    print(f"[create_testing_log] Logging failure: {title_tag} (label: {label})")

    try:
        screenshot_url = push_screenshot(screenshot_path, pat, test_name, browser)
    except Exception as exc:
        print(f"[create_testing_log] ERROR pushing screenshot: {exc}", file=sys.stderr)
        return None

    try:
        existing_issue = find_existing_issue(title_tag, pat)
    except Exception as exc:
        print(f"[create_testing_log] ERROR checking for existing issues: {exc}", file=sys.stderr)
        return None

    # Duplicate check: has this exact test+browser already failed and been
    # filed before? If so, don't create a second issue for the same
    # problem -- just comment that it happened again, with the new evidence.
    if existing_issue is not None:
        print(f"[create_testing_log] Found existing issue #{existing_issue['number']} -- treating as a re-occurrence.")
        try:
            comment_body = _build_reoccurrence_comment(error_message, screenshot_url)
            add_comment_to_issue(existing_issue["number"], comment_body, pat)
            add_label_to_issue(existing_issue["number"], label, pat)
        except Exception as exc:
            print(f"[create_testing_log] ERROR commenting on existing issue: {exc}", file=sys.stderr)
            return None
        # Status is already "Testing log" from when the issue was first
        # filed -- nothing to update there for a re-occurrence.
        print(f"[create_testing_log] Done (re-occurrence): {existing_issue['html_url']}")
        return existing_issue["html_url"]

    # No existing issue for this test -- create one, then file it under
    # "Testing log" on the project board.
    try:
        body = _build_new_issue_body(test_name, browser, error_message, stack_trace, screenshot_url, analysis)
        issue = create_issue(title, body, label, pat)
    except Exception as exc:
        print(f"[create_testing_log] ERROR creating issue: {exc}", file=sys.stderr)
        return None

    try:
        project_id, field_id, option_id = get_project_status_field(pat)
        item_id = add_issue_to_project(issue["node_id"], project_id, pat)
        set_status_field(project_id, item_id, field_id, option_id, pat)
        print(f"[create_testing_log] Added issue to project and set Status to '{STATUS_OPTION_NAME}'.")
    except Exception as exc:
        print(f"[create_testing_log] ERROR adding issue to project: {exc}", file=sys.stderr)
        return issue["html_url"]

    print(f"[create_testing_log] Done: {issue['html_url']}")
    return issue["html_url"]


def main():
    parser = argparse.ArgumentParser(description="File a GitHub issue + project entry for a failing test.")
    parser.add_argument("test_name")
    parser.add_argument("browser")
    parser.add_argument("error_message")
    parser.add_argument("screenshot_path")
    parser.add_argument(
        "--stack-trace",
        default=None,
        help="Optional stack trace, improves the rule-based root-cause analysis.",
    )
    args = parser.parse_args()

    result = create_testing_log(
        args.test_name,
        args.browser,
        args.error_message,
        args.screenshot_path,
        stack_trace=args.stack_trace,
    )
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()