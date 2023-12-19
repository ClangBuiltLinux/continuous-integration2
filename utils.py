import json
import os
from pathlib import Path
import sys
from typing import Dict, Optional
import urllib.request

import yaml

CI_ROOT = Path(__file__).resolve().parent


def get_config_from_generator():
    # Trusted input.
    # https://github.com/yaml/pyyaml/wiki/PyYAML-yaml.load(input)-Deprecation
    try:
        with Path(CI_ROOT, "generator.yml").open(encoding='utf-8') as file:
            return yaml.load(file, Loader=yaml.FullLoader)
    except FileNotFoundError as err:
        print_red("generator.yml not found?")
        raise err


def get_image_name():
    arch = os.environ["ARCH"]
    if arch == "powerpc":
        subarch = get_cbl_name()
        return {
            "ppc32": "uImage",
            "ppc64": "vmlinux",
            "ppc64le": "zImage.epapr"
        }[subarch]
    return {
        "arm": "zImage",
        "arm64": "Image.gz",
        "i386": "bzImage",
        "loongarch": "vmlinuz.efi",
        "mips": "vmlinux",
        "riscv": "Image",
        "s390": "bzImage",
        "um": "linux",
        "x86_64": "bzImage",
    }[arch]


def get_cbl_name():
    arch = os.environ["ARCH"]
    full_config = os.environ["CONFIG"]
    base_config = full_config.split("+")[0]

    # Distribution configurations have a URL
    if "https://" in base_config:
        if "alpine" in base_config:
            alpine_to_cbl = {
                "aarch64": "arm64",
                "armv7": "arm32_v7",
                "riscv64": "riscv",
                "x86_64": "x86_64"
            }
            # The URL is https://.../config-edge.<arch>
            alpine_arch = base_config.split(".")[-1]
            return alpine_to_cbl[alpine_arch]
        if "fedora" in base_config:
            fedora_to_cbl = {
                "aarch64": "arm64",
                "armv7hl": "arm32_v7",
                "i686": "x86",
                "ppc64le": "ppc64le",
                "s390x": "s390",
                "x86_64": "x86_64"
            }
            # The URL is https://.../kernel-<arch>-fedora.config
            fedora_arch = base_config.split("/")[-1].split("-")[1]
            return fedora_to_cbl[fedora_arch]
        if "openSUSE" in base_config:
            suse_to_cbl = {
                "arm64": "arm64",
                "armv7hl": "arm32_v7",
                "i386": "x86",
                "ppc64le": "ppc64le",
                "riscv64": "riscv",
                "s390x": "s390",
                "x86_64": "x86_64"
            }
            # The URL is https://.../<arch>/default
            suse_arch = base_config.split("/")[-2]
            return suse_to_cbl[suse_arch]
        # Arch Linux is x86_64 only
        if "archlinux" in base_config:
            return "x86_64"

    # ChromeOS configurations have the architecture as the second to last
    # folder of the second config fragment path:
    # chromeos/config/chromeos/arm64/common.config
    # chromeos/config/chromeos/x86_64/common.config
    if "chromeos" in base_config:
        return full_config.split("+")[1].split("/")[-2]

    unique_defconfigs = {
        "multi_v5_defconfig": "arm32_v5",
        "aspeed_g5_defconfig": "arm32_v6",
        "multi_v7_defconfig": "arm32_v7",
        "malta_defconfig": "mipsel",
        "ppc44x_defconfig": "ppc32",
        "ppc64_guest_defconfig": "ppc64",
        "powernv_defconfig": "ppc64le",
    }
    if "CONFIG_CPU_BIG_ENDIAN=y" in full_config:
        if arch == "arm64":
            return "arm64be"
        if arch == "mips":
            return "mips"
    if base_config in unique_defconfigs:
        return unique_defconfigs[base_config]
    if "defconfig" in base_config or "virtconfig" in base_config:
        return "x86" if arch == "i386" else arch
    raise RuntimeError("unknown CBL name")


def _read_builds():
    file = "mock.builds.json" if os.environ.get("MOCK") else "builds.json"
    try:
        if (builds := Path(CI_ROOT, file)).stat().st_size == 0:
            raise RuntimeError(f"{file} is zero sized?")
        builds_json = json.loads(builds.read_text(encoding='utf-8'))
    except FileNotFoundError as err:
        print_red(f"Unable to find {file}. Artifact not saved?")
        raise err
    return builds_json["builds"].values()


def get_requested_llvm_version():
    ver = os.environ["LLVM_VERSION"]
    with Path(CI_ROOT, "LLVM_TOT_VERSION").open(encoding='utf-8') as file:
        llvm_tot_version = str(int(file.read())).strip()
    return "clang-" + ("nightly" if ver == llvm_tot_version else ver)


def show_builds():
    print_yellow("Available builds:")
    for build in _read_builds():
        arch_val = build['target_arch']
        llvm_version_val = build['toolchain'].split('-', 1)[1]
        config_val = "+".join(build["kconfig"])
        print_yellow(
            f"\tARCH={arch_val} LLVM_VERSION={llvm_version_val} CONFIG={config_val}"
        )


def get_build():
    arch = os.environ["ARCH"]
    configs = os.environ["CONFIG"].split("+")
    llvm_version = get_requested_llvm_version()
    for build in _read_builds():
        if build["target_arch"] == arch and \
           build["toolchain"] == llvm_version and \
           build["kconfig"] == configs:
            return build
    print_red("Unable to find build")
    show_builds()
    sys.exit(1)


def get_repo_ref(config, tree_name):
    for tree in config["trees"]:
        if tree["name"] == tree_name:
            return tree["git_repo"], tree["git_ref"]
    raise RuntimeError(f"Could not find git repo and ref for {tree_name}?")


def get_llvm_versions(config, tree_name):
    llvm_versions = set()
    repo, ref = get_repo_ref(config, tree_name)
    for build in config["builds"]:
        if build["git_repo"] == repo and build["git_ref"] == ref:
            llvm_versions.add(build["llvm_version"])
    return llvm_versions


def get_workflow_name_to_var_name(workflow_name: str) -> str:
    """
    GitHub Repository Variables have special formatting rules:
        * Alphanumeric characters ([a-z], [A-Z], [0-9]) or underscores (_) only.
        * Spaces are not allowed.
        * Cannot start with a number.
        * Cannot start with GITHUB_ prefix.
    """

    workflow_name = workflow_name.replace(" ", "_")

    return "_" + "".join([x for x in workflow_name if x.isalnum()]).upper()


def update_repository_variable(
    key: str,
    http_headers: Dict[str, str],
    *,
    sha: Optional[str] = None,
    clang_version: Optional[str] = None,
    build_status: Optional[str] = None,
    other: Optional[Dict[str, str]] = None,
    allow_fail_to_pass=False  # should a cache entry be allowed to go from 'fail' to 'pass'
):
    """
    Update cache entries.

    Only non-None fields are updated, the others remain as they are in the cache.

    Use `other` to provide more values than what is supported as keyword args.
    """
    url = f"https://api.github.com/repos/ClangBuiltLinux/continuous-integration2/actions/variables/{key}"

    # this REPO_SCOPED_PAT comes from GitHub Actions repository secrets
    # if we aren't running in a workflow a KeyError is raised and caught by caller
    # you may manually set this in your environment as well.
    request = urllib.request.Request(url, headers=http_headers)

    with urllib.request.urlopen(request) as response:
        content = response.read().decode("utf-8")
        data = json.loads(content)
        cached_value = json.loads(data["value"])
        print(f"{cached_value=}")
        if sha:
            cached_value["linux_sha"] = sha
        if clang_version:
            cached_value["clang_version"] = clang_version
        if build_status:
            if not allow_fail_to_pass and cached_value[
                    'build_status'] == 'fail' and build_status == 'pass':
                ...
            else:
                cached_value["build_status"] = build_status
        if other and isinstance(other, dict):
            for k, v in other.items():
                cached_value[k] = v

        cached_value = json.dumps(cached_value)

    new_value = json.dumps({
        "name": key,
        "value": cached_value
    }).encode("utf-8")
    update_request = urllib.request.Request(url,
                                            data=new_value,
                                            method="PATCH",
                                            headers=http_headers)
    urllib.request.urlopen(update_request)  # pylint: disable=consider-using-with

    print(
        f"Updated cache entry with key '{key}' to status '{build_status}' at sha '{sha}' and clang_version '{clang_version}'\n"
        f"other fields: {other}")


def print_red(msg):
    print(f"\033[91m{msg}\033[0m", file=sys.stderr)
    sys.stderr.flush()


def print_yellow(msg):
    print(f"\033[93m{msg}\033[0m", file=sys.stdout)
    sys.stdout.flush()


def patch_series_flag(tree):
    patches_folder = Path('patches', tree)
    patch_files = list(Path(CI_ROOT, patches_folder).glob('*.patch'))
    return f"--patch-series {patches_folder} " if patch_files else ""
