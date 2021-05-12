import json
import os
import pathlib
import sys


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
        "mips": "vmlinux",
        "riscv": "Image",
        "s390": "bzImage",
        "x86_64": "bzImage",
    }[arch]


def get_cbl_name():
    arch = os.environ["ARCH"]
    full_config = os.environ["CONFIG"]
    base_config = full_config.split("+")[0]

    unique_defconfigs = {
        "multi_v5_defconfig": "arm32_v5",
        "aspeed_g5_defconfig": "arm32_v6",
        "multi_v7_defconfig": "arm32_v7",
        "malta_defconfig": "mipsel",
        "ppc44x_defconfig": "ppc32",
        "pseries_defconfig": "ppc64",
        "powernv_defconfig": "ppc64le",
    }
    if "CONFIG_CPU_BIG_ENDIAN=y" in full_config:
        if arch == "arm64":
            return "arm64be"
        if arch == "mips":
            return "mips"
    if base_config in unique_defconfigs:
        return unique_defconfigs[base_config]
    if "defconfig" in base_config:
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
    ci_folder = pathlib.Path(__file__).resolve().parent
    with open(ci_folder.joinpath("LLVM_TOT_VERSION")) as f:
        llvm_tot_version = int(f.read())
    return "clang-" + ("nightly" if ver == llvm_tot_version else str(ver))


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
    sys.exit(1)


def print_red(msg):
    print("\033[91m%s\033[0m" % msg, file=sys.stderr)


def print_yellow(msg):
    print("\033[93m%s\033[0m" % msg)
