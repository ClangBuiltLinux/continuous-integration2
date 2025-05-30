#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys
import yaml

from utils import CI_ROOT, LLVM_TOT_VERSION, disable_subsys_werror_configs, get_config_from_generator, get_repo_ref, get_llvm_versions, patch_series_flag


# Aliases makes this YAML unreadable
# https://ttl255.com/yaml-anchors-and-aliases-and-how-to-disable-them/
class NoAliasDumper(yaml.SafeDumper):

    def ignore_aliases(self, _data):
        return True


def parse_args(trees):
    parser = argparse.ArgumentParser(description="Generate TuxSuite YML.")
    parser.add_argument("tree",
                        help="The git repo and ref to filter in.",
                        choices=[tree["name"] for tree in trees])
    return parser.parse_args()


def emit_tuxsuite_yml(config, tree, llvm_version):
    toolchain = f"clang-{llvm_version}"
    tuxsuite_yml = f"tuxsuite/{tree}-{toolchain}.tux.yml"
    repo, ref = get_repo_ref(config, tree)

    with Path(CI_ROOT, tuxsuite_yml).open("w", encoding='utf-8') as file:
        orig_stdout = sys.stdout
        sys.stdout = file

        print("# DO NOT MODIFY MANUALLY!")
        print("# This file has been autogenerated by invoking:")
        print(f"# $ ./generate_tuxsuite.py {tree}")
        print("# Invoke tuxsuite via:")
        patches_flag = patch_series_flag(tree)
        print(
            f"# $ tuxsuite plan --git-repo {repo} --git-ref {ref} --job-name defconfigs --json-out builds.json {patches_flag}{tuxsuite_yml}"
        )
        print("# Invoke locally via:")
        print(f"# $ git clone -b {ref} --depth=1 {repo} linux")
        if patches_flag:
            # Input: '--patch-series ... '
            # Output: '...'
            patches_folder = patches_flag.split(' ')[1]
            print(
                f"# $ git -C linux quiltimport --patches ../{patches_folder}")
        print(
            f"# $ scripts/build-local.py -C linux -f {tuxsuite_yml} -j defconfigs"
        )

        tuxsuite_plan = {
            'version': 1,
            'name': f"{repo} at {ref}",
            'description': f"{repo} at {ref}",
            'jobs': [
                {
                    'name': 'defconfigs',
                    'builds': [],
                }
            ]
        }  # yapf: disable
        max_version = int(LLVM_TOT_VERSION.read_text(encoding='utf-8'))
        defconfigs = []
        distribution_configs = []
        allconfigs = []
        for build in config["builds"]:
            if build["git_repo"] == repo and \
               build["git_ref"] == ref and \
               build["llvm_version"] == llvm_version:
                arch = build.get("ARCH", "x86_64")
                if llvm_version == max_version:
                    tuxsuite_toolchain = "clang-nightly"
                elif llvm_version == "android":
                    tuxsuite_toolchain = "clang-android"
                else:
                    # We want to use the kernel.org LLVM builds for speed but
                    # we don't want korg everywhere
                    tuxsuite_toolchain = f"korg-{toolchain}"

                disable_subsys_werror_configs(build["config"])
                current_build = {
                    "target_arch": arch,
                    "toolchain": tuxsuite_toolchain,
                    "kconfig": build["config"],
                    "targets": build["targets"]
                }
                if "kernel_image" in build:
                    current_build.update(
                        {"kernel_image": build["kernel_image"]})
                if "make_variables" in build:
                    current_build.update(
                        {"make_variables": build["make_variables"]})

                cfg_str = str(build["config"])
                if "defconfig" in cfg_str:
                    defconfigs.append(current_build)
                elif "https://" in cfg_str:
                    distribution_configs.append(current_build)
                else:
                    allconfigs.append(current_build)

        tuxsuite_plan["jobs"][0]["builds"] = defconfigs
        if distribution_configs:
            tuxsuite_plan["jobs"] += [{
                "name": "distribution_configs",
                "builds": distribution_configs
            }]
        if allconfigs:
            tuxsuite_plan["jobs"] += [{
                "name": "allconfigs",
                "builds": allconfigs
            }]
        print(
            yaml.dump(tuxsuite_plan,
                      Dumper=NoAliasDumper,
                      width=1000,
                      sort_keys=False))
        sys.stdout = orig_stdout


if __name__ == "__main__":
    # The list of valid trees come from the input, so we parse the input, then
    # check command line flags.
    generated_config = get_config_from_generator()
    args = parse_args(generated_config["trees"])
    for llvm_ver in get_llvm_versions(generated_config, args.tree):
        emit_tuxsuite_yml(generated_config, args.tree, llvm_ver)
