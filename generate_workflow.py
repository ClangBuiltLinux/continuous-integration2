#!/usr/bin/env python3

import argparse
import hashlib
import yaml
import sys


def parse_args(trees):
    parser = argparse.ArgumentParser(description="Generate GitHub Action Workflow YAML.")
    parser.add_argument("tree", help="The git repo and ref to filter in.",
            choices=[tree["name"] for tree in trees])
    return parser.parse_args()


def get_config():
    return yaml.load(sys.stdin, Loader=yaml.FullLoader)


def get_fragment():
    with open("job_fragment.yml", "r") as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def get_repo_ref(config, tree_name):
    for tree in config["trees"]:
        if tree["name"] == tree_name:
            return tree["git_repo"], tree["git_ref"]


def get_job_name(build):
    return "ARCH=" + (build["ARCH"] if "ARCH" in build else "x86_64") \
    + " LLVM=" + str(int(build["llvm"])) + " LLVM_IAS=" + str(int(build["llvm_ias"])) \
    + " BOOT=" + str(int(build["boot"])) + " LLVM " + str(int(build["llvm_version"])) \
    + " " + build["config"]


def sanitize_job_name(name):
    h = hashlib.new("md5", name.encode("utf-8"), usedForSecurity=False)
    return "_" + h.hexdigest()


def get_steps(build):
    name = get_job_name(build)
    return {
        sanitize_job_name(name): {
            "runs-on": "ubuntu-20.04",
            "needs": "kick_tuxsuite",
            "name": name,
            "env": {
                "ARCH": build["ARCH"] if "ARCH" in build else "x86_64",
                "LLVM": build["llvm"],
                "LLVM_VERSION": build["llvm_version"],
                "LLVM_IAS": build["llvm_ias"],
                "INSTALL_DEPS": 1,
                "BOOT": build["boot"],
                "CONFIG": build["config"],
            },
            "steps": [{
                    "uses": "actions/checkout@v2",
                    "with": { "submodules": True },
                }, {
                    "uses": "actions/download-artifact@v2",
                    "with": { "name": "output_artifact" },
                }, {
                    "name": "Boot Test",
                    "run": "./check_logs.py",
                },
            ],
        }
    }


def print_builds(config, tree_name):
    repo, ref = get_repo_ref(config, tree_name)
    fragment = get_fragment()
    fragment["name"] = tree_name
    # Bug in yaml.load()???
    fragment["on"] = fragment[True]
    del fragment[True]
    fragment["jobs"]["kick_tuxsuite"]["steps"][1]["run"] = \
            "tuxsuite build-set --set-name foo-bar --json-out builds.json --tux-config tuxsuite/{}.tux.yml || true".format(\
            tree_name)

    for build in config["builds"]:
        if build["git_repo"] == repo and build["git_ref"] == ref:
            steps = get_steps(build)
            fragment["jobs"].update(steps)
    print("# DO NOT MODIFY MANUALLY!")
    print("# This file has been autogenerated by invoking:")
    print("# $ ./generate_workflow.py < generator.yml {} > .github/workflows/{}.yml".format(tree_name, tree_name))
    print(yaml.dump(fragment, Dumper=yaml.Dumper, width=1000, sort_keys=False))


if __name__ == "__main__":
    config = get_config()
    args = parse_args(config["trees"])
    print_builds(config, args.tree)
