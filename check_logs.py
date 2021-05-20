#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import urllib.request

from utils import get_build, get_image_name, print_red, print_yellow, get_cbl_name
from install_deps import install_deps


def fetch_logs(build):
    url = build["download_url"] + "build.log"
    print_yellow("fetching logs from %s" % build["download_url"])
    # TODO: use something more robust like python wget library.
    response = urllib.request.urlopen(url).read().decode("UTF-8")
    print(response)


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
    print_yellow("fetching DTB from: %s" % url)
    urllib.request.urlretrieve(url, dtb_path)
    if os.path.exists:
        print_yellow("Filesize: %d" % os.path.getsize(dtb_path))
    else:
        print_red("Unable to download dtb")
        sys.exit(1)


def fetch_kernel_image(build):
    image_name = get_image_name()
    url = build["download_url"] + image_name
    print_yellow("fetching kernel image from: %s" % url)
    # TODO: use something more robust like python wget library.
    urllib.request.urlretrieve(url, image_name)
    # Suspect download is failing.
    if os.path.exists:
        print_yellow("Filesize: %d" % os.path.getsize(image_name))
    else:
        print_red("Unable to download kernel image")
        sys.exit(1)


def cwd():
    os.chdir(os.path.dirname(__file__))
    return os.getcwd()


def run_boot():
    cbl_arch = get_cbl_name()
    kernel_image = cwd() + "/" + get_image_name()
    boot_qemu = [
        "./boot-utils/boot-qemu.sh", "-a", cbl_arch, "-k", kernel_image
    ]
    if cbl_arch == "s390":
        boot_qemu += ["--use-cbl-qemu"]
    try:
        subprocess.run(boot_qemu, check=True)
    except subprocess.CalledProcessError as e:
        if e.returncode == 124:
            print_red("Image failed to boot")
        raise e


def boot_test(build):
    if build["errors_count"] > 0:
        print_red("errors encountered during build, skipping boot")
        sys.exit(1)
    if "BOOT" in os.environ and os.environ["BOOT"] == "0":
        print_yellow("boot test disabled via config, skipping boot")
        return
    fetch_kernel_image(build)
    fetch_dtb(build)
    install_deps()
    run_boot()


if __name__ == "__main__":
    for var in ["ARCH", "CONFIG", "LLVM_VERSION"]:
        if not var in os.environ:
            print_red("$%s must be specified" % var)
            sys.exit(1)
    build = get_build()
    print(json.dumps(build, indent=4))
    check_log(build)
    boot_test(build)
