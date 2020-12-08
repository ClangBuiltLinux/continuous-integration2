import json
import os
import sys


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
        "mips": "vmlinux",
        "riscv": "Image.gz",
        "s390": "bzImage",
        "x86_64": "bzImage",
    }[arch]


def get_image_path():
    config = os.environ["CONFIG"]
    if config == "i386_defconfig":
        return "arch/x86/boot/"

    arch = os.environ["ARCH"]
    return {
        "arm": "arch/arm/boot/",
        "arm64": "arch/arm64/boot/",
        "mips": "arch/mips/boot/",
        "powerpc": "arch/powerpc/boot/",
        "riscv": "arch/riscv/boot/",
        "s390": "arch/s390/boot/",
        # "x86": "arch/x86/boot/",
        "x86_64": "arch/x86_64/boot/",
    }[arch]


def get_cbl_name():
    arch = os.environ["ARCH"]
    config = os.environ["CONFIG"]

    unique_defconfigs = {
        "multi_v5_defconfig": "arm32_v5",
        "aspeed_g5_defconfig": "arm32_v6",
        "multi_v7_defconfig": "arm32_v7",
        "malta_kvm_guest_defconfig": "mips",
        "ppc44x_defconfig": "ppc32",
        "pseries_defconfig": "ppc64",
        "powernv_defconfig": "ppc64le",
        "i386_defconfig": "x86",
    }
    if config in unique_defconfigs:
        return unique_defconfigs[config]
    if config == "defconfig":
        return arch
    raise Exception("unknown CBL name")


def _read_builds():
    try:
        with open("builds.json") as f:
            builds = json.load(f)
    except FileNotFoundError as e:
        print_red("Unable to find builds.json. Artifact not saved?")
        raise e
    return builds


def get_build():
    arch = os.environ["ARCH"]
    config = os.environ["CONFIG"]
    for build in _read_builds():
        if build["target_arch"] == arch and build["kconfig"][0] == config:
            return build
    print_red("Unable to find build")
    sys.exit(1)


def print_red(msg):
    print("\033[91m%s\033[0m" % msg, file=sys.stderr)


def print_yellow(msg):
    print("\033[93m%s\033[0m" % msg)
