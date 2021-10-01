#!/usr/bin/env python3

import glob
import json
import os
import subprocess
import sys
import time
import urllib.request

from utils import get_build, get_image_name, print_red, print_yellow, get_cbl_name, show_builds
from install_deps import install_deps


def _fetch(title, url, dest):
    print_yellow("fetching %s from: %s" % (title, url))
    # TODO: use something more robust like python wget library.
    retries = 0
    max_retries = 7
    retry_codes = [500, 504]
    while retries < max_retries:
        try:
            if retries:
                time.sleep(2**retries)
            retries += 1
            urllib.request.urlretrieve(url, dest)
            break
        except ConnectionResetError as err:
            print_yellow('%s download error ("%s"), retrying...' %
                         (title, str(err)))
            pass
        except urllib.error.HTTPError as err:
            if err.code in retry_codes:
                print_yellow("%s download error (%d), retrying..." %
                             (title, err.code))
                pass
            elif err.code == 404:
                print_red(
                    "%s could not be found (404 error), did the build timeout?"
                    % (title))
                sys.exit(1)
            else:
                print_red("%d error trying to download %s" % (err.code, title))
                sys.exit(1)
        except urllib.error.URLError as err:
            print_yellow('%s download error ("%s"), retrying...' %
                         (title, str(err)))
            pass

    if retries == max_retries:
        print_red("Unable to download %s after %d tries" %
                  (title, max_retries))
        sys.exit(1)

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


def fetch_built_config(build):
    url = build["download_url"] + "config"
    _fetch("built .config", url, ".config")


def check_built_config(build):
    # Only check built configs if we have specific CONFIGs requested.
    custom = False
    for config in build["kconfig"]:
        if 'CONFIG' in config:
            custom = True
    if not custom:
        return

    fetch_built_config(build)
    # Build dictionary of CONFIG_NAME: y/m/n ("is not set" translates to 'n').
    configs = dict()
    for line in open(".config"):
        line = line.strip()
        if len(line) == 0:
            continue

        name = None
        state = None
        if '=' in line:
            name, state = line.split('=', 1)
        elif line.startswith("# CONFIG_"):
            name, state = line.split(" ", 2)[1:]
            if state != "is not set":
                print_yellow("Could not parse '%s' from .config line '%s'!?" %
                             (name, line))
            state = 'n'
        elif not line.startswith("#"):
            print_yellow("Could not parse .config line '%s'!?" % (line))
        configs[name] = state

    # Compare requested configs against the loaded dictionary.
    fail = False
    for config in build["kconfig"]:
        if not 'CONFIG' in config:
            continue
        name, state = config.split('=')
        # If a config is missing from the dictionary, it is considered 'n'.
        if state != configs.get(name, 'n'):
            print_red("FAIL: %s not found in .config!" % (config))
            fail = True
        else:
            print("ok: %s=%s" % (name, state))
    if fail:
        sys.exit(1)


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
        if "CONFIG_KASAN_KUNIT_TEST=y" in build["kconfig"] or \
           "CONFIG_KCSAN_KUNIT_TEST=y" in build["kconfig"]:
            print_yellow(
                "Disabling Oops problem matcher under Sanitizer KUnit build")
            print("::remove-matcher owner=linux-kernel-oopses")

    # Before spawning a process with potentially different IO buffering,
    # flush the existing buffers so output is ordered correctly.
    sys.stdout.flush()
    sys.stderr.flush()

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
    print_yellow("Register clang error/warning problem matchers")
    for problem_matcher in glob.glob(".github/problem-matchers/*.json"):
        print("::add-matcher::%s" % (problem_matcher))
    check_log(build)
    check_built_config(build)
    boot_test(build)
