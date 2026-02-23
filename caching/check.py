#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "pyyaml>=6.0.3",
#     "requests>=2.32.5",
# ]
# ///
"""
Don't run this script directly, let the CI invoke it and determine whether a
workflow should run or not.

The workflow will run if any of the following conditions are true:
    1) This Workflow Name is not present in our Repository Variables
    2) The Workflow Name is present but the "linux_sha" or "clang_version"
       do not match the current versions (cache miss)
    3) The cached build_status is not pass or fail

The workflow will _not_ run if the following condition is true:
    1) A Repository Variable with a key matching our workflow name is found
       and it has fields "linux_sha" and "clang_version" matching the current
       run (cache hit)
    2) The cached build_status is pass or fail

An exit code of '0' means that no Tuxsuite jobs will run while an exit code of
'1' means that Tuxsuite will proceed.

In either case, a Repository Variable with a key matching this Workflow Name
will be created/updated matching the current linux_sha and clang_version
detected. This ensures that our next run has the highest possible chance of a
cache hit.

When a new cache entry is created, it will have a build_status of "presuite"
to signify that it has yet to be built by Tuxsuite. Upon completion of Tuxsuite,
a new build_status is assigned to the cache entry by check_logs.py. Importantly,
we want to only cache on a "pass" or "fail" status as these mean that Tuxsuite
actually completed its work and didnt timeout.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from typing import Optional

import requests

from utils import get_patches_hash, get_workflow_name_to_var_name, update_repository_variable

OWNER = "ClangBuiltLinux"
REPO = "continuous-integration2"
MAIN_BRANCH = "main"
headers = {}  # populated after args are parsed

# states we allow our cache system to perform a cache-hit upon
# other states like 'presuite' or 'unknown' or '' (empty) are considered
# poisoned and untrustworthy so we should launch the builds.
# check_logs.py is responsible for populating the build_status field of the cache
CACHE_HITABLE_STATES = ("pass", "fail")
TIMEOUT = 64


class MalformedCacheError(Exception):
    ...


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("-g", "--github-token", required=True, type=str)
    parser.add_argument("-w", "--workflow-name", required=True, type=str)
    parser.add_argument("-o", "--git-repo", required=True, type=str)  # url
    parser.add_argument("-r", "--git-ref", required=True, type=str)
    parser.add_argument("--purge-cache", required=False, action="store_true")

    return parser.parse_args()


def get_sha_from_git_ref(git_repo: str, git_ref: str):
    res = subprocess.run(
        ["git", "ls-remote", git_repo, "--git-ref", git_ref],
        capture_output=True,
        text=True,
        check=True,
    )
    pattern = r"^[0-9a-z]*"

    if (match := re.search(r"^[0-9a-z]*", res.stdout)) is None:
        print(
            f"Could not get git sha from tree {git_repo} at ref {git_ref}.\n"
            f"Subprocess returned: {res.stdout}\n"
            f"Which doesn't have any matches with this pattern: {pattern}\n"
            f"Expecting something like this: be59bee58790f9d137cfc11973e856e4f8ab3888	refs/tags/v6.7-rc5"
        )
        sys.exit(1)

    return match.group()


def ___purge___cache___():
    """!!!completely clears the CBL CI cache!!!"""
    list_url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/variables"

    list_response = requests.get(list_url, headers=headers, timeout=TIMEOUT)
    print(list_response.content)
    all_variables_keys = [
        x["name"] for x in json.loads(list_response.content)["variables"]
        if x["name"].startswith("_")
    ]

    for key in all_variables_keys:
        delete_url = (
            f"https://api.github.com/repos/{OWNER}/{REPO}/actions/variables/{key}"
        )
        delete_response = requests.delete(delete_url,
                                          headers=headers,
                                          timeout=TIMEOUT)
        if delete_response.status_code != 204:
            print(f"ERROR: Couldn't delete cache entry with key {key}")
            sys.exit(1)

    print("CACHE CLEARED")


def get_clang_version():
    """
    Get the current clang version info string.

    When check_cache.py is run by a Github workflow we are in a container
    using the specific toolchain version that Tuxmake plans to use in its
    upcoming build(s).
    """
    res = subprocess.run(
        ["clang", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )

    return res.stdout.splitlines()[0].strip()


def get_repository_variable_or_none(name: str) -> Optional[dict]:
    _url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/variables/{name}"

    response = requests.get(_url, headers=headers, timeout=TIMEOUT)
    if response.status_code != 200:
        return None

    as_dict = json.loads(response.content.decode())
    return json.loads(as_dict["value"])


def create_repository_variable(name: str, linux_sha: str, clang_version: str,
                               patches_hash: str) -> None:
    _url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/variables"

    _value = json.dumps({
        "linux_sha": linux_sha,
        "clang_version": clang_version,
        "patches_hash": patches_hash,
        "build_status": "presuite",
    })
    data = {"name": name, "value": _value}

    resp = requests.post(_url, headers=headers, json=data, timeout=TIMEOUT)
    print(f"create_repository_variable() response:\n{resp.content}")


if __name__ == "__main__":
    args = parse_args()

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {args.github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if args.purge_cache:
        ___purge___cache___()
        sys.exit(1)

    VAR_NAME = get_workflow_name_to_var_name(args.workflow_name)
    tree_name = args.workflow_name.split(' ', 1)[0]

    curr_sha = get_sha_from_git_ref(args.git_repo, args.git_ref)
    curr_clang_version = get_clang_version()
    # pylint: disable-next=invalid-name
    curr_patches_hash = get_patches_hash(tree_name)
    print(f"""\
        Current sha: {curr_sha}
        Current Clang Version: {curr_clang_version}
        Current patches hash: {curr_patches_hash}
    """)

    # pull down repo variable
    result = get_repository_variable_or_none(VAR_NAME)
    if result is None:
        print(f"CACHE MISS: Did not find repo variable {VAR_NAME} "
              f"from workflow_name: {args.workflow_name}. Creating it now.")
        create_repository_variable(
            VAR_NAME,
            linux_sha=curr_sha,
            clang_version=curr_clang_version,
            patches_hash=curr_patches_hash,
        )
        sys.exit(1)

    # excess fields are OK but these fields are mandatory for caching.
    missing_fields = []
    for field in ("linux_sha", "clang_version", "build_status"):
        if field not in result:
            missing_fields.append(field)

    if len(missing_fields) > 0:
        raise MalformedCacheError(
            f"The cache with key {VAR_NAME} based on workflow '{args.workflow_name}' "
            f"is one or more fields. It's missing: {missing_fields}\n"
            f"The current cache looks as follows:\n{result}.")

    cached_sha = result["linux_sha"]
    cached_clang_version = result["clang_version"]
    cached_build_status = result["build_status"]
    cached_patches_hash = result.get("patches_hash", curr_patches_hash)

    if cached_sha != curr_sha or cached_clang_version != curr_clang_version or cached_patches_hash != curr_patches_hash:
        print(f"""\
            CACHE MISS: current linux_sha is {curr_sha}, clang_version is {curr_clang_version},
            and current patches_hash is {curr_patches_hash} while {args.workflow_name} has
            a cached linux_sha of {cached_sha}, a cached clang_version of {cached_clang_version},
            and a cached patches_hash of {cached_patches_hash}.

            Repository Variable key: {VAR_NAME}
            Updating cache now.
        """)
        update_repository_variable(
            VAR_NAME,
            http_headers=headers,
            sha=curr_sha,
            clang_version=curr_clang_version,
            patches_hash=curr_patches_hash,
            build_status="presuite",
        )
        sys.exit(1)

    # we cache hit, but we only want to allow certain states to be cacheable
    # other states are dodgy and we're better off rerunning the builds just in case
    if (stripped := cached_build_status.strip()) not in CACHE_HITABLE_STATES:
        print(f"""\
            CACHE HIT: Both the linux_sha and the clang_version match
            However, the previous build status ({stripped}) is not a status
            that check_cache.py is configured to support. The status should be
            one of {CACHE_HITABLE_STATES}.
            Running the Tuxsuite builds now.
        """)
        sys.exit(1)

    print(f"""\
        CACHE HIT: The linux_sha, clang_version, and patches hash match
        CACHE:  {cached_sha} | {cached_clang_version} | {cached_patches_hash}
        ACTUAL: {curr_sha} | {curr_clang_version} | {curr_patches_hash}
        Not running this workflow as it would be redundant.
        CACHED STATUS: {cached_build_status}
    """)

    env_file = os.getenv("GITHUB_ENV", None)
    if env_file is not None:
        with open(env_file, "a", encoding="utf-8") as fd:
            fd.write(f"CACHE_PASS={cached_build_status.strip()}")

    sys.exit(
        0)  # signifies to the workflow that no jobs should run ('success')
