#!/usr/bin/env python3
"""Turn a single Playwright test failure into a permanent GitHub record.

Given a failing test's name, browser, error message, and a screenshot file,
this module:

  1. Copies the screenshot into evidence/ in *this* repo (dummy-testing-agent),
     commits it, and pushes it to the current branch -- so it gets a
     permanent raw.githubusercontent.com URL.
  2. Opens a GitHub Issue on udhaya-ud-gen/dummy-app with the error message
     and the pushed screenshot embedded.
  3. Adds that issue to udhaya-ud-gen's GitHub Project (number 1) and sets
     its "Status" field to the "Testing log" option.

Requires the GH_PAT environment variable: a GitHub personal access token
with repo (issues + contents) and project scopes.

Usage (standalone CLI):
    python agent/create_testing_log.py "Valid Login" chromium "Timeout ..." /path/to/screenshot.png

Usage (as a library, e.g. from run_pipeline.py):
    from create_testing_log import create_testing_log
    create_testing_log(test_name, browser, error_message, screenshot_path)
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests

# --- Configuration -------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = REPO_ROOT / "evidence"

ISSUE_OWNER = "udhaya-ud-gen"
ISSUE_REPO = "dummy-app"          # repo the failure issue gets filed in

PROJECT_OWNER = "udhaya-ud-gen"   # user who owns the GitHub Project
PROJECT_NUMBER = 1
STATUS_FIELD_NAME = "Status"
STATUS_OPTION_NAME = "Testing log"

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


def push_screenshot(screenshot_path, pat):
    """Copy the screenshot into evidence/, commit it, and push to the
    current branch using the PAT for auth. Returns the resulting
    raw.githubusercontent.com URL.
    """
    screenshot_path = Path(screenshot_path)
    if not screenshot_path.is_file():
        raise FileNotFoundError(f"Screenshot not found: {screenshot_path}")

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    # Make the destination filename unique so repeated failures don't
    # clobber each other's evidence files.
    code, short_sha, _ = _run_git("rev-parse", "--short", "HEAD")
    suffix = short_sha if code == 0 and short_sha else "nogit"
    dest_name = f"{screenshot_path.stem}-{suffix}-{os.getpid()}{screenshot_path.suffix}"
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


def create_issue(test_name, browser, error_message, screenshot_url, pat):
    """Create the GitHub Issue on ISSUE_OWNER/ISSUE_REPO. Returns the parsed
    JSON response (contains 'html_url', 'node_id', 'number', etc.)."""
    title = f"[Test Failure] {test_name} ({browser})"
    body = (
        f"**Error:**\n\n```\n{error_message}\n```\n\n"
        f"**Screenshot:**\n\n![screenshot]({screenshot_url})\n"
    )

    response = requests.post(
        f"{GITHUB_API}/repos/{ISSUE_OWNER}/{ISSUE_REPO}/issues",
        json={"title": title, "body": body},
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


def _graphql(query, variables, pat):
    """Run a single GraphQL query/mutation against the GitHub API."""
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


def create_testing_log(test_name, browser, error_message, screenshot_path):
    """End-to-end: push screenshot evidence, file an issue, and add it to
    the project's 'Testing log' column.

    Each stage prints a clear success/error message. A failure in a later
    stage does not undo earlier stages (e.g. if the project step fails, the
    issue that was already created is still returned) -- this keeps a batch
    caller (run_pipeline.py) able to move on to the next failing test.

    Returns the created issue's HTML URL, or None if the issue itself could
    not be created.
    """
    pat = _get_pat()
    print(f"[create_testing_log] Logging failure: {test_name} ({browser})")

    try:
        screenshot_url = push_screenshot(screenshot_path, pat)
    except Exception as exc:
        print(f"[create_testing_log] ERROR pushing screenshot: {exc}", file=sys.stderr)
        return None

    try:
        issue = create_issue(test_name, browser, error_message, screenshot_url, pat)
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
    args = parser.parse_args()

    result = create_testing_log(args.test_name, args.browser, args.error_message, args.screenshot_path)
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
