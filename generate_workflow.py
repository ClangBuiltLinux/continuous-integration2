#!/usr/bin/env python3

import argparse
import hashlib
import pathlib
import sys
import yaml

from utils import get_config, get_llvm_versions, get_repo_ref, patch_series_flag, print_red


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
                    # Always run on the main branch
                    "main",
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
        "jobs": {}
    } # yapf: disable


def print_config(build):
    config = build["config"]
    if type(config) is list:
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
    h = hashlib.new("md5", name.encode("utf-8"))
    return "_" + h.hexdigest()


def tuxsuite_setups(build_set, tuxsuite_yml):
    patch_series = patch_series_flag(
        tuxsuite_yml.split("/")[1].split("-clang-")[0])
    return {
        "kick_tuxsuite_{}".format(build_set): {
            "name": "TuxSuite ({})".format(build_set),
            # https://docs.github.com/en/free-pro-team@latest/actions/reference/workflow-syntax-for-github-actions#jobsjob_idruns-on
            "runs-on": "ubuntu-latest",
            "container": "tuxsuite/tuxsuite",
            "env": {
                "TUXSUITE_TOKEN": "${{ secrets.TUXSUITE_TOKEN }}"
            },
            "steps": [
                {
                    "uses": "actions/checkout@v3"
                },
                {
                    "name": "tuxsuite",
                    "run": "tuxsuite build-set --set-name {} --json-out builds.json --tux-config {}{} || true".format(build_set, tuxsuite_yml, patch_series)
                },
                {
                    "name": "save output",
                    "uses": "actions/upload-artifact@v2",
                    "with": {
                        "path": "builds.json",
                        "name": "output_artifact_{}".format(build_set),
                        "if-no-files-found": "error"
                    },
                }
            ]
        }
    } # yapf: disable


def get_steps(build, build_set):
    name = get_job_name(build)
    return {
        sanitize_job_name(name): {
            "runs-on": "ubuntu-latest",
            "needs": "kick_tuxsuite_{}".format(build_set),
            "name": name,
            "env": {
                "ARCH": build["ARCH"] if "ARCH" in build else "x86_64",
                "LLVM_VERSION": build["llvm_version"],
                "BOOT": int(build["boot"]),
                "CONFIG": print_config(build),
            },
            "container": "ghcr.io/clangbuiltlinux/qemu",
            "steps": [
                {
                    "uses": "actions/checkout@v2",
                    "with": {
                        "submodules": True
                    },
                },
                {
                    "uses": "actions/download-artifact@v2",
                    "with": {
                        "name": "output_artifact_{}".format(build_set)
                    },
                },
                {
                    "name": "Check Build and Boot Logs",
                    "run": "./check_logs.py",
                },
            ],
        }
    } # yapf: disable


def get_cron_schedule(schedules, tree_name, llvm_version):
    for item in schedules:
        if item["name"] == tree_name and \
           item["llvm_version"] == llvm_version:
            return item["schedule"]
    print_red("Could not find schedule for {} clang-{}?".format(
        tree_name, llvm_version))
    exit(1)


def print_builds(config, tree_name, llvm_version):
    repo, ref = get_repo_ref(config, tree_name)
    toolchain = "clang-{}".format(llvm_version)
    tuxsuite_yml = "tuxsuite/{}-{}.tux.yml".format(tree_name, toolchain)
    github_yml = ".github/workflows/{}-{}.yml".format(tree_name, toolchain)

    check_logs_defconfigs = {}
    check_logs_distribution_configs = {}
    check_logs_allconfigs = {}
    for build in config["builds"]:
        if build["git_repo"] == repo and \
           build["git_ref"] == ref and \
           build["llvm_version"] == llvm_version:
            if "defconfig" in str(build["config"]):
                check_logs_defconfigs.update(get_steps(build, "defconfigs"))
            elif "https://" in str(build["config"]):
                check_logs_distribution_configs.update(
                    get_steps(build, "distribution_configs"))
            else:
                check_logs_allconfigs.update(get_steps(build, "allconfigs"))

    workflow_name = "{} ({})".format(tree_name, toolchain)
    cron_schedule = get_cron_schedule(config["tree_schedules"], tree_name,
                                      llvm_version)
    workflow = initial_workflow(workflow_name, cron_schedule, tuxsuite_yml,
                                github_yml)
    workflow["jobs"].update(tuxsuite_setups("defconfigs", tuxsuite_yml))
    workflow["jobs"].update(check_logs_defconfigs)

    if check_logs_distribution_configs:
        workflow["jobs"].update(
            tuxsuite_setups("distribution_configs", tuxsuite_yml))
        workflow["jobs"].update(check_logs_distribution_configs)

    if check_logs_allconfigs:
        workflow["jobs"].update(tuxsuite_setups("allconfigs", tuxsuite_yml))
        workflow["jobs"].update(check_logs_allconfigs)

    with open(github_yml, "w") as f:
        orig_stdout = sys.stdout
        sys.stdout = f
        print("# DO NOT MODIFY MANUALLY!")
        print("# This file has been autogenerated by invoking:")
        print("# $ ./generate_workflow.py {}".format(tree_name))
        print(
            yaml.dump(workflow,
                      Dumper=yaml.Dumper,
                      width=1000,
                      sort_keys=False))
        sys.stdout = orig_stdout


if __name__ == "__main__":
    config = get_config()
    args = parse_args(config["trees"])
    for llvm_version in get_llvm_versions(config, args.tree):
        print_builds(config, args.tree, llvm_version)
