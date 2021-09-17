#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import urllib.request

from utils import get_build, get_image_name, print_red, print_yellow, get_cbl_name, show_builds
from install_deps import install_deps


def _fetch(title, url, dest):
    print_yellow("fetching %s from: %s" % (title, url))
    # TODO: use something more robust like python wget library.
    urllib.request.urlretrieve(url, dest)
    if os.path.exists(dest):
        print_yellow("Filesize: %d" % os.path.getsize(dest))
    else:
        print_red("Unable to download %s" % (title))
        sys.exit(1)


def fetch_logs(build):
    log = "build.log"
    url = build["download_url"] + log
    _fetch("logs", url, log)
    print(open(log).read())


def check_log(build):
    warnings_count = build["warnings_count"]
    errors_count = build["errors_count"]
    if warnings_count + errors_count > 0:
        print_yellow("%d warnings, %d errors" % (warnings_count, errors_count))
        fetch_logs(build)


def fetch_dtb(build):
    config = os.environ["CONFIG"]
    if config != "multi_v5_defconfig" and config != "aspeed_g5_defconfig":
        return
    dtb = {
        "multi_v5_defconfig": "aspeed-bmc-opp-palmetto.dtb",
        "aspeed_g5_defconfig": "aspeed-bmc-opp-romulus.dtb",
    }[config]
    dtb_path = "dtbs/" + dtb
    url = build["download_url"] + dtb_path
    # mkdir -p
    os.makedirs(dtb_path.split("/")[0], exist_ok=True)
    _fetch("DTB", url, dtb_path)


def fetch_kernel_image(build):
    image_name = get_image_name()
    url = build["download_url"] + image_name
    _fetch("kernel image", url, image_name)


def cwd():
    os.chdir(os.path.dirname(__file__))
    return os.getcwd()


def run_boot(build):
    cbl_arch = get_cbl_name()
    kernel_image = cwd() + "/" + get_image_name()
    boot_qemu = [
        "./boot-utils/boot-qemu.sh", "-a", cbl_arch, "-k", kernel_image
    ]
    if cbl_arch == "s390":
        boot_qemu += ["--use-cbl-qemu"]
    # If we are running a sanitizer build, we should increase the number of
    # cores and timeout because booting is much slower
    if "CONFIG_KASAN=y" in build["kconfig"] or \
       "CONFIG_KCSAN=y" in build["kconfig"] or \
       "CONFIG_UBSAN=y" in build["kconfig"]:
        boot_qemu += ["-s", "4"]
        if "CONFIG_KASAN=y" in build["kconfig"]:
            boot_qemu += ["-t", "20m"]
        else:
            boot_qemu += ["-t", "10m"]
    try:
        subprocess.run(boot_qemu, check=True)
    except subprocess.CalledProcessError as e:
        if e.returncode == 124:
            print_red("Image failed to boot")
        raise e


def boot_test(build):
    if build["result"] == "fail":
        print_red("fatal build errors encountered during build, skipping boot")
        sys.exit(1)
    if "BOOT" in os.environ and os.environ["BOOT"] == "0":
        print_yellow("boot test disabled via config, skipping boot")
        return
    fetch_kernel_image(build)
    fetch_dtb(build)
    install_deps()
    run_boot(build)


if __name__ == "__main__":
    missing = []
    for var in ["ARCH", "CONFIG", "LLVM_VERSION"]:
        if not var in os.environ:
            missing.append(var)
    if len(missing):
        for var in missing:
            print_red("$%s must be specified" % var)
        show_builds()
        sys.exit(1)
    build = get_build()
    print(json.dumps(build, indent=4))
    check_log(build)
    boot_test(build)
