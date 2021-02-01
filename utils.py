import json
import os
import sys

# TODO: brittle, we should parse generator.yml for this, but requires adding
# pyyaml dependency to workers...
TOT_LLVM = 12


def get_image_name():
    arch = os.environ["ARCH"]
    # "ppc32": "uImage",
    # "ppc64": "vmlinux",
    # "ppc64le": "zImage.epapr",
    if arch == "powerpc":
        return "zImage.epapr"
    return {
        "arm": "zImage",
        "arm64": "Image.gz",
        "i386": "bzImage",
        "mips": "vmlinux",
        "riscv": "Image.gz",
        "s390": "bzImage",
        "x86_64": "bzImage",
    }[arch]


def get_cbl_name():
    arch = os.environ["ARCH"]
    config = os.environ["CONFIG"].split("+")[0]

    unique_defconfigs = {
        "multi_v5_defconfig": "arm32_v5",
        "aspeed_g5_defconfig": "arm32_v6",
        "multi_v7_defconfig": "arm32_v7",
        "malta_kvm_guest_defconfig": "mips",
        "ppc44x_defconfig": "ppc32",
        "pseries_defconfig": "ppc64",
        "powernv_defconfig": "ppc64le",
    }
    if config in unique_defconfigs:
        return unique_defconfigs[config]
    if "defconfig" in config:
        return "x86" if arch == "i386" else arch
    raise Exception("unknown CBL name")


def _read_builds():
    try:
        with open("builds.json") as f:
            builds = json.load(f)
    except FileNotFoundError as e:
        print_red("Unable to find builds.json. Artifact not saved?")
        raise e
    return builds


def get_requested_llvm_version():
    ver = int(os.environ["LLVM_VERSION"])
    return "clang-" + ("nightly" if ver == TOT_LLVM else str(ver))


def get_build():
    arch = os.environ["ARCH"]
    configs = sorted(os.environ["CONFIG"].split("+"))
    llvm_version = get_requested_llvm_version()
    for build in _read_builds():
        if build["target_arch"] == arch and \
           build["toolchain"] == llvm_version and \
           sorted(build["kconfig"]) == configs:
            return build
    print_red("Unable to find build")
    sys.exit(1)


def print_red(msg):
    print("\033[91m%s\033[0m" % msg, file=sys.stderr)


def print_yellow(msg):
    print("\033[93m%s\033[0m" % msg)
