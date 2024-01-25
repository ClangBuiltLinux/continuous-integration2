"""
Run within a kick_tuxsuite_foo job.

Analyze the outputted builds.json and update our cache accordingly.

If _all_ builds passed we can safely update our cache with a "pass" build_status.

However, if any build fails or times out, we will mark it as either "fail" or
"badtux", respectively.

To clarify "badtux", it just means Tuxsuite had an issue outside of just building
its targets; something like a timeout or instance crash. In these instances,
"badtux" (or any non "pass" or "fail") build status signifies to our caching
system to not cache. The idea being that we want to rerun these jobs and not have
a caching system stop us from doing so -- even if sha and version match.
"""

import json
import os
import sys
from pathlib import Path

from utils import get_workflow_name_to_var_name, update_repository_variable

if "GITHUB_WORKFLOW" not in os.environ:
    print("Couldn't find GITHUB_WORKFLOW in env. Not in a GitHub Workflow?")
    sys.exit(1)

MOCK = "MOCK" in os.environ


def update_cache(status: str, git_sha: str, clang_version: str):
    print(f"Trying to update cache with status: {status}")
    cache_entry_key = get_workflow_name_to_var_name(
        os.environ["GITHUB_WORKFLOW"])

    if "REPO_SCOPED_PAT" not in os.environ:
        print(
            "Couldn't find REPO_SCOPED_PAT in env. Not in a GitHub Workflow?")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {os.environ['REPO_SCOPED_PAT']}"}

    update_repository_variable(
        cache_entry_key,
        http_headers=headers,
        build_status=status,
        sha=git_sha,
        clang_version=clang_version,
        # prevent overriding a 'fail' to a 'pass'
        allow_fail_to_pass=False,
    )


def main():
    builds_json = Path(("mock." if MOCK else "") + "builds.json")

    print(f"Reading {builds_json}")
    raw = builds_json.read_text(encoding="utf-8")

    builds = json.loads(raw)["builds"]

    if len(builds) == 0:
        print("No builds present. Did Tuxsuite run?")
        sys.exit(1)

    # let's grab sha and version info as Tuxsuite has the most up-to-date info
    builds_that_are_missing_metadata = []
    git_sha = None
    clang_version = None
    for entry, build in builds.items():
        try:
            git_sha = build["git_sha"]
            clang_version = build["tuxmake_metadata"]["compiler"][
                "version_full"]
            break
        except KeyError:
            builds_that_are_missing_metadata.append(entry)

    if len(builds_that_are_missing_metadata) == len(builds):
        raise RuntimeError(
            f"Could not find a suitable git sha or compiler version in any build\n"
            f"Here's the build.json:\n{raw}")

    if len(builds_that_are_missing_metadata) > 0:
        print(
            "Warning: Some of the builds in builds.json are malformed and missing "
            "some metadata.\n"
            f"Here's a list: {builds_that_are_missing_metadata}\n"
            f"Here's the build.json in question:\n{raw}")

    assert git_sha and clang_version

    print(f"Tuxsuite {git_sha = } | {clang_version = }")

    for _, info in builds.items():
        if info["tuxbuild_status"] != "complete":
            update_cache("badtux", git_sha, clang_version)
            sys.exit(0)
        if (status := info["build_status"]) != "pass":
            update_cache(status, git_sha, clang_version)
            sys.exit(0)

    # only if all builds completed and passed will we set this status
    update_cache("pass", git_sha, clang_version)
    sys.exit(0)


if __name__ == "__main__":
    main()
