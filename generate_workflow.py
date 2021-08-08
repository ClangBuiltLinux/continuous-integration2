#!/usr/bin/env python3

import argparse
import hashlib
import yaml
import sys


def parse_args(trees):
    parser = argparse.ArgumentParser(
        description="Generate GitHub Action Workflow YAML.")
    parser.add_argument("tree",
                        help="The git repo and ref to filter in.",
                        choices=[tree["name"] for tree in trees])
    return parser.parse_args()


def get_config():
    return yaml.load(sys.stdin, Loader=yaml.FullLoader)


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


def get_repo_ref(config, tree_name):
    for tree in config["trees"]:
        if tree["name"] == tree_name:
            return tree["git_repo"], tree["git_ref"]


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
    # LLVM_IAS=0 is the default. Only show when we have opted into LLVM_IAS.
    if build["llvm_ias"]:
        job += " LLVM_IAS=1"
    # Having "LLVM <VER>" is a little hard to parse, make it look like
    # an environment variable
    job += " LLVM_VERSION=" + str(build["llvm_version"])
    job += " " + print_config(build)
    return job


def sanitize_job_name(name):
    h = hashlib.new("md5", name.encode("utf-8"))
    return "_" + h.hexdigest()


def tuxsuite_setups(build_set, tuxsuite_yml):
    return {
        "kick_tuxsuite_{}".format(build_set): {
            "name": "TuxSuite ({})".format(build_set),
            # https://docs.github.com/en/free-pro-team@latest/actions/reference/workflow-syntax-for-github-actions#jobsjob_idruns-on
            "runs-on": "ubuntu-20.04",
            "container": "tuxsuite/tuxsuite",
            "env": {
                "TUXSUITE_TOKEN": "${{ secrets.TUXSUITE_TOKEN }}"
            },
            "steps": [
                {
                    "uses": "actions/checkout@v2"
                },
                {
                    "name": "tuxsuite",
                    "run": "tuxsuite build-set --set-name {} --json-out builds.json --tux-config {} || true".format(build_set, tuxsuite_yml)
                },
                {
                    "name": "save output",
                    "uses": "actions/upload-artifact@v2",
                    "with": {
                        "path": "builds.json",
                        "name": "output_artifact_{}".format(build_set)
                    },
                }
            ]
        }
    } # yapf: disable


def get_steps(build, build_set):
    name = get_job_name(build)
    return {
        sanitize_job_name(name): {
            "runs-on": "ubuntu-20.04",
            "needs": "kick_tuxsuite_{}".format(build_set),
            "name": name,
            "env": {
                "ARCH": build["ARCH"] if "ARCH" in build else "x86_64",
                "LLVM_VERSION": build["llvm_version"],
                "INSTALL_DEPS": 1,
                "BOOT": int(build["boot"]),
                "CONFIG": print_config(build),
            },
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
                    "name": "Register clang error/warning problem matcher",
                    "run": 'echo "::add-matcher::.github/problem-matchers/clang-errors-warnings.json"'
                },
                {
                    "name": "Boot Test",
                    "run": "./check_logs.py",
                },
            ],
        }
    } # yapf: disable


def print_builds(config, tree_name):
    repo, ref = get_repo_ref(config, tree_name)
    tuxsuite_yml = "tuxsuite/{}.tux.yml".format(tree_name)
    github_yml = ".github/workflows/{}.yml".format(tree_name)

    check_logs_defconfigs = {}
    check_logs_distribution_configs = {}
    check_logs_allconfigs = {}
    for build in config["builds"]:
        if build["git_repo"] == repo and build["git_ref"] == ref:
            cron_schedule = build["schedule"]
            if "defconfig" in str(build["config"]):
                check_logs_defconfigs.update(get_steps(build, "defconfigs"))
            elif "https://" in str(build["config"]):
                check_logs_distribution_configs.update(
                    get_steps(build, "distribution_configs"))
            else:
                check_logs_allconfigs.update(get_steps(build, "allconfigs"))

    workflow = initial_workflow(tree_name, cron_schedule, tuxsuite_yml,
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

    print("# DO NOT MODIFY MANUALLY!")
    print("# This file has been autogenerated by invoking:")
    print("# $ ./generate_workflow.py < generator.yml {} > {}".format(
        tree_name, github_yml))
    print(yaml.dump(workflow, Dumper=yaml.Dumper, width=1000, sort_keys=False))


if __name__ == "__main__":
    config = get_config()
    args = parse_args(config["trees"])
    print_builds(config, args.tree)
