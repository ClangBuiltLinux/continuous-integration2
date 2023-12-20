#!/usr/bin/env python3

import argparse
import hashlib
from pathlib import Path
import sys
import yaml

from utils import CI_ROOT, get_config_from_generator, get_llvm_versions, get_repo_ref, patch_series_flag, print_red


def parse_args(trees):
    parser = argparse.ArgumentParser(
        description="Generate GitHub Action Workflow YAML.")
    parser.add_argument("tree",
                        help="The git repo and ref to filter in.",
                        choices=[tree["name"] for tree in trees])
    return parser.parse_args()


def initial_workflow(name, cron, tuxsuite_yml, workflow_yml):
    return {
        "name": name,
        "on": {
            # https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions#onpushpull_requestpaths
            "push": {
                "branches": [
                    # Allow testing on branches with a presubmit/ prefix
                    "presubmit/*"
                ],
                "paths": [
                    "check_logs.py",
                    "utils.py",
                    tuxsuite_yml,
                    workflow_yml
                ]
            },
            # https://docs.github.com/en/free-pro-team@latest/actions/reference/events-that-trigger-workflows#scheduled-events
            "schedule": [
                {"cron": cron}
            ],
            # https://docs.github.com/en/free-pro-team@latest/actions/reference/events-that-trigger-workflows#workflow_dispatch
            "workflow_dispatch": None
        },
        "permissions": "read-all",
        "jobs": {}
    }  # yapf: disable


def print_config(build):
    config = build["config"]
    if isinstance(config, list):
        config_name = config[0]
        i = 1
        while i < len(config):
            config_name += "+" + config[i]
            i += 1
    else:
        config_name = config
    return config_name


def get_job_name(build):
    job = "ARCH=" + (build["ARCH"] if "ARCH" in build else "x86_64")
    # BOOT=1 is the default, only show if we have disabled it
    if not build["boot"]:
        job += " BOOT=0"
    # LLVM=0 does not make much sense. Translate LLVM=0 into CC=clang
    if build["llvm"]:
        job += " LLVM=1"
    else:
        job += " CC=clang"
    # If LD was specified, show what it is
    if "make_variables" in build and "LD" in build["make_variables"]:
        job += " LD=" + str(build["make_variables"]["LD"])
    job += " LLVM_IAS=" + str(build["make_variables"]["LLVM_IAS"])
    # Having "LLVM <VER>" is a little hard to parse, make it look like
    # an environment variable
    job += " LLVM_VERSION=" + str(build["llvm_version"])
    job += " " + print_config(build)
    return job


def sanitize_job_name(name):
    return "_" + hashlib.new("md5", name.encode("utf-8")).hexdigest()


def check_cache_job_setup(repo, ref, toolchain):
    with open("LLVM_TOT_VERSION", encoding='utf-8') as fd:
        llvm_tot_version = fd.read().strip()

    last_part = toolchain.split("-")[-1]
    if last_part == llvm_tot_version:
        toolchain = "clang-nightly"

    return {
        "check_cache": {
            "name":
            "Check Cache",
            "runs-on":
            "ubuntu-latest",
            "container":
            f"tuxmake/x86_64_{toolchain}",
            "env": {
                "GIT_REPO": repo,
                "GIT_REF": ref
            },
            "outputs": {
                "output": "${{ steps.step2.outputs.output }}",
                "status": "${{ steps.step2.outputs.status }}"
            },
            "steps": [
                {
                    "uses": "actions/checkout@v4"
                },
                {
                    "name": "pip install -r requirements.txt",
                    "run":
                    "apt-get install -y python3-pip && pip install -r requirements.txt"
                },
                {
                    "name":
                    "python check_cache.py",
                    "id":
                    "step1",
                    "continue-on-error":
                    True,
                    "run":
                    "python check_cache.py -w '${{github.workflow}}' "
                    "-g ${{secrets.REPO_SCOPED_PAT}} "
                    "-r ${{env.GIT_REF}} "
                    "-o ${{env.GIT_REPO}}",
                },
                {
                    "name":
                    "Save exit code to GITHUB_OUTPUT",
                    "id":
                    "step2",
                    "run":
                    'echo "output=${{steps.step1.outcome}}" >> "$GITHUB_OUTPUT" && echo "status=$CACHE_PASS" >> "$GITHUB_OUTPUT"',
                },
            ],
        }
    }


def tuxsuite_setups(job_name, tuxsuite_yml, repo, ref):
    patch_series = patch_series_flag(
        tuxsuite_yml.split("/")[1].split("-clang-")[0])
    cond = {"if": "${{needs.check_cache.outputs.output == 'failure' || github.event_name == 'workflow_dispatch'}}"}  # yapf: disable
    return {
        f"kick_tuxsuite_{job_name}": {
            "name": f"TuxSuite ({job_name})",
            # https://docs.github.com/en/free-pro-team@latest/actions/reference/workflow-syntax-for-github-actions#jobsjob_idruns-on
            "runs-on": "ubuntu-latest",
            "container": "tuxsuite/tuxsuite",
            "needs": "check_cache",
            "env": {
                "TUXSUITE_TOKEN": "${{ secrets.TUXSUITE_TOKEN }}",
                "REPO_SCOPED_PAT": "${{ secrets.REPO_SCOPED_PAT }}"
            },
            "timeout-minutes": 480,
            "steps": [
                {
                    "name": "Checking Cache Pass",
                    "if": "${{ needs.check_cache.outputs.output == 'success' && github.event_name != 'workflow_dispatch' && needs.check_cache.outputs.status == 'pass'}}",
                    "run": "echo 'Cache HIT on previously PASSED build. Passing this build to avoid redundant work.' && exit 0"
                },
                {
                    "name": "Checking Cache Fail",
                    "if": "${{ needs.check_cache.outputs.output == 'success' && github.event_name != 'workflow_dispatch' && needs.check_cache.outputs.status == 'fail'}}",
                    "run": "echo 'Cache HIT on previously FAILED build. Failing this build to avoid redundant work.' && exit 1"
                },
                {
                    "uses": "actions/checkout@v4",
                    **cond,
                },
                {
                    "name": "tuxsuite",
                    **cond,
                    "run": f"tuxsuite plan --git-repo {repo} --git-ref {ref} --job-name {job_name} --json-out builds.json {patch_series}{tuxsuite_yml} || true",
                },
                {
                    "name": "Update Cache Build Status",
                    **cond,
                    "run": "python update_cache.py"
                },
                {
                    "name": "save builds.json",
                    **cond,
                    "uses": "actions/upload-artifact@v3",
                    "with": {
                        "path": "builds.json",
                        "name": f"output_artifact_{job_name}",
                        "if-no-files-found": "error"
                    },
                },
                {
                    'name': 'generate boot-utils.json',
                    **cond,
                    'run': 'python3 scripts/generate-boot-utils-json.py ${{ secrets.GITHUB_TOKEN }}',
                },
                {
                    'name': 'save boot-utils.json',
                    **cond,
                    'uses': 'actions/upload-artifact@v3',
                    'with': {
                        'path': 'boot-utils.json',
                        'name': f"boot_utils_json_{job_name}",
                        'if-no-files-found': 'error',
                    },
                },
            ]
        }
    }  # yapf: disable


def get_steps(build, build_set):
    name = get_job_name(build)
    return {
        sanitize_job_name(name): {
            "runs-on": "ubuntu-latest",
            "needs": [f"kick_tuxsuite_{build_set}", "check_cache"],
            "name": name,
            "if": "${{needs.check_cache.outputs.status != 'pass'}}",
            "env": {
                "ARCH": build["ARCH"] if "ARCH" in build else "x86_64",
                "LLVM_VERSION": build["llvm_version"],
                "BOOT": int(build["boot"]),
                "CONFIG": print_config(build),
                "REPO_SCOPED_PAT": "${{ secrets.REPO_SCOPED_PAT }}"
            },
            "container": {
                "image": "ghcr.io/clangbuiltlinux/qemu",
                "options": "--ipc=host",
            },
            "steps": [
                {
                    "uses": "actions/checkout@v4",
                    "with": {
                        "submodules": True
                    },
                },
                {
                    "uses": "actions/download-artifact@v3",
                    "with": {
                        "name": f"output_artifact_{build_set}"
                    },
                },
                {
                    "uses": "actions/download-artifact@v3",
                    "with": {
                        "name": f"boot_utils_json_{build_set}"
                    },
                },
                {
                    "name": "Check Build and Boot Logs",
                    "run": "./check_logs.py",
                },
            ],
        }
    }  # yapf: disable


def get_cron_schedule(schedules, tree_name, llvm_version):
    for item in schedules:
        if item["name"] == tree_name and \
           item["llvm_version"] == llvm_version:
            return item["schedule"]
    print_red(f"Could not find schedule for {tree_name} clang-{llvm_version}?")
    sys.exit(1)


def print_builds(config, tree_name, llvm_version):
    repo, ref = get_repo_ref(config, tree_name)
    toolchain = f"clang-{llvm_version}"
    tuxsuite_yml = f"tuxsuite/{tree_name}-{toolchain}.tux.yml"
    github_yml = f".github/workflows/{tree_name}-{toolchain}.yml"

    check_logs_defconfigs = {}
    check_logs_distribution_configs = {}
    check_logs_allconfigs = {}
    for build in config["builds"]:
        if build["git_repo"] == repo and \
           build["git_ref"] == ref and \
           build["llvm_version"] == llvm_version:
            cfg_str = str(build["config"])
            if "defconfig" in cfg_str or "chromeos" in cfg_str:
                check_logs_defconfigs.update(get_steps(build, "defconfigs"))
            elif "https://" in cfg_str:
                check_logs_distribution_configs.update(
                    get_steps(build, "distribution_configs"))
            else:
                check_logs_allconfigs.update(get_steps(build, "allconfigs"))

    workflow_name = f"{tree_name} ({toolchain})"
    cron_schedule = get_cron_schedule(config["tree_schedules"], tree_name,
                                      llvm_version)
    workflow = initial_workflow(workflow_name, cron_schedule, tuxsuite_yml,
                                github_yml)

    workflow['jobs'].update(check_cache_job_setup(repo, ref, toolchain))
    workflow["jobs"].update(
        tuxsuite_setups("defconfigs", tuxsuite_yml, repo, ref))
    workflow["jobs"].update(check_logs_defconfigs)

    if check_logs_distribution_configs:
        workflow["jobs"].update(
            tuxsuite_setups("distribution_configs", tuxsuite_yml, repo, ref))
        workflow["jobs"].update(check_logs_distribution_configs)

    if check_logs_allconfigs:
        workflow["jobs"].update(
            tuxsuite_setups("allconfigs", tuxsuite_yml, repo, ref))
        workflow["jobs"].update(check_logs_allconfigs)

    with Path(CI_ROOT, github_yml).open("w", encoding='utf-8') as file:
        orig_stdout = sys.stdout
        sys.stdout = file
        print("# DO NOT MODIFY MANUALLY!")
        print("# This file has been autogenerated by invoking:")
        print(f"# $ ./generate_workflow.py {tree_name}")
        print(
            yaml.dump(workflow,
                      Dumper=yaml.Dumper,
                      width=1000,
                      sort_keys=False))
        sys.stdout = orig_stdout


if __name__ == "__main__":
    generated_config = get_config_from_generator()
    args = parse_args(generated_config["trees"])
    for llvm_ver in get_llvm_versions(generated_config, args.tree):
        print_builds(generated_config, args.tree, llvm_ver)
