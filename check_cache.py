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
from typing import Optional
from sys import exit
import requests
import subprocess
import json
import os
import re
from utils import get_workflow_name_to_var_name, update_repository_variable

OWNER = "ClangBuiltLinux"
REPO = "continuous-integration2"
MAIN_BRANCH = "main"
HEADERS = {}  # populated after args are parsed

# states we allow our cache system to perform a cache-hit upon
# other states like 'presuite' or 'unknown' or '' (empty) are considered
# poisoned and untrustworthy so we should launch the builds.
# check_logs.py is responsible for populating the build_status field of the cache
CACHE_HITABLE_STATES = ("pass", "fail")


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
    result = subprocess.run(
        ["git", "ls-remote", git_repo, "--git-ref", git_ref],
        capture_output=True,
        text=True,
        check=True,
    )
    pattern = r"^[0-9a-z]*"

    if (match := re.search(r"^[0-9a-z]*", result.stdout)) is None:
        print(
            f"Could not get git sha from tree {git_repo} at ref {git_ref}.\n"
            f"Subprocess returned: {result.stdout}\n"
            f"Which doesn't have any matches with this pattern: {pattern}\n"
            f"Expecting something like this: be59bee58790f9d137cfc11973e856e4f8ab3888	refs/tags/v6.7-rc5"
        )
        exit(1)

    return match.group()


def ___purge___cache___():
    """!!!completely clears the CBL CI cache!!!"""
    list_url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/variables"

    list_response = requests.get(list_url, headers=HEADERS)
    print(list_response.content)
    all_variables_keys = [
        x["name"]
        for x in json.loads(list_response.content)["variables"]
        if x["name"].startswith("_")
    ]

    for key in all_variables_keys:
        delete_url = (
            f"https://api.github.com/repos/{OWNER}/{REPO}/actions/variables/{key}"
        )
        delete_response = requests.delete(delete_url, headers=HEADERS)
        if delete_response.status_code != 204:
            print(f"ERROR: Couldn't delete cache entry with key {key}")
            exit(1)

    print("CACHE CLEARED")


def get_clang_version():
    """
    Get the current clang version info string.

    When check_cache.py is run by a Github workflow we are in a container
    using the specific toolchain version that Tuxmake plans to use in its
    upcoming build(s).
    """
    result = subprocess.run(
        ["clang", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )

    return result.stdout.splitlines()[0].strip()


def get_repository_variable_or_none(name: str) -> Optional[dict]:
    _url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/variables/{name}"

    response = requests.get(_url, headers=HEADERS)
    if response.status_code != 200:
        return None

    # TODO: add some error handling if this json parse fails
    as_dict = json.loads(response.content.decode())
    return json.loads(as_dict["value"])


def create_repository_variable(name: str, linux_sha: str, clang_version: str) -> None:
    _url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/variables"

    _value = json.dumps(
        {
            "linux_sha": linux_sha,
            "clang_version": clang_version,
            "build_status": "presuite",
        }
    )
    data = {"name": name, "value": _value}

    resp = requests.post(_url, headers=HEADERS, json=data)
    print(f"create_repository_variable() response:\n{resp.content}")


if __name__ == "__main__":
    args = parse_args()

    HEADERS = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {args.github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if args.purge_cache:
        ___purge___cache___()
        exit(1)

    var_name = get_workflow_name_to_var_name(args.workflow_name)

    sha = get_sha_from_git_ref(args.git_repo, args.git_ref)
    clang_version = get_clang_version()
    print(f"Current sha: {sha}\nCurrent Clang Version: {clang_version}")

    # pull down repo variable
    result = get_repository_variable_or_none(var_name)
    if result is None:
        print(
            f"CACHE MISS: Did not find repo variable {var_name} "
            f"from workflow_name: {args.workflow_name}. Creating it now."
        )
        create_repository_variable(
            var_name,
            linux_sha=sha,
            clang_version=clang_version,
        )
        exit(1)

    # excess fields are OK but these fields are mandatory for caching.
    missing_fields = []
    for field in ("linux_sha", "clang_version", "build_status"):
        if field not in result:
            missing_fields.append(field)

    if len(missing_fields):
        raise MalformedCacheError(
            f"The cache with key {var_name} based on workflow '{args.workflow_name}' "
            f"is one or more fields. It's missing: {missing_fields}\n"
            f"The current cache looks as follows:\n{result}."
        )
        exit(1)  # unreachable, but makes this code path like the others

    cached_sha = result["linux_sha"]
    cached_clang_version = result["clang_version"]
    cached_build_status = result["build_status"]

    if cached_sha != sha or cached_clang_version != clang_version:
        print(
            f"CACHE MISS: current linux_sha is {sha} and clang_version is {clang_version} "
            f"while {args.workflow_name} has a cached linux_sha of {cached_sha} "
            f"and a cached clang_version of {cached_clang_version} under "
            f"Repository Variable key: {var_name}\nUpdating cache now."
        )
        update_repository_variable(
            var_name,
            http_headers=HEADERS,
            sha=sha,
            clang_version=clang_version,
            build_status="presuite",
        )
        exit(1)

    # we cache hit, but we only want to allow certain states to be cacheable
    # other states are dodgy and we're better off rerunning the builds just in case
    if (stripped := cached_build_status.strip()) not in CACHE_HITABLE_STATES:
        print(
            f"CACHE HIT: Both the linux_sha and the clang_version match\n"
            f"However, the previous build status ({stripped}) is not a status "
            f"that check_cache.py is configured to support. The status should be "
            f"one of {CACHE_HITABLE_STATES}.\nRunning the Tuxsuite builds now."
        )
        exit(1)

    print(
        f"CACHE HIT: Both the linux_sha and the clang_version match\n"
        f"CACHE:  {cached_sha} | {cached_clang_version}\nACTUAL: {sha} | {clang_version}\n"
        f"Not running this workflow as it would be redundant.\n"
        f"CACHED STATUS: {cached_build_status}"
    )

    env_file = os.getenv("GITHUB_ENV", None)
    if env_file is not None:
        with open(env_file, "a") as fd:
            fd.write(f"CACHE_PASS={cached_build_status.strip()}")

    exit(0)  # signifies to the workflow that no jobs should run ('success')
