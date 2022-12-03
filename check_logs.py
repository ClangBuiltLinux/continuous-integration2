#!/usr/bin/env python3

import glob
import json
import os
import subprocess
import sys
import time
import urllib.request

from utils import get_build, get_image_name, get_requested_llvm_version, print_red, print_yellow, get_cbl_name, show_builds


def _fetch(title, url, dest):
    current_time = time.strftime("%H:%M:%S", time.localtime())
    print_yellow(f"{current_time}: fetching {title} from: {url}")
    # TODO: use something more robust like python wget library.
    retries = 0
    max_retries = 7
    retry_codes = [404, 500, 504]
    while retries < max_retries:
        try:
            if retries:
                time.sleep(2**retries)
            retries += 1
            urllib.request.urlretrieve(url, dest)
            break
        except ConnectionResetError as err:
            print_yellow(f"{title} download error ('{str(err)}'), retrying...")
            pass
        except urllib.error.HTTPError as err:
            if err.code in retry_codes:
                print_yellow(
                    f"{title} download error ({err.code}), retrying...")
                pass
            else:
                print_red(f"{err.code} error trying to download {title}")
                sys.exit(1)
        except urllib.error.URLError as err:
            print_yellow(f"{title} download error ('{str(err)}'), retrying...")
            pass

    if retries == max_retries:
        print_red(f"Unable to download {title} after {max_retries} tries")
        sys.exit(1)

    if os.path.exists(dest):
        print_yellow(f"Filesize: {os.path.getsize(dest)}")
    else:
        print_red(f"Unable to download {title}")
        sys.exit(1)


def verify_build():
    build = get_build()

    # If the build was neither fail nor pass, we need to fetch the status.json
    # of the particular build to try and get an updated result. We attempt this
    # up to 9 times.
    retries = 0
    max_retries = 9
    while retries < max_retries:
        if build["tuxbuild_status"] == "complete":
            break

        if retries:
            time.sleep(2**retries)
        retries += 1

        status_json = "status.json"
        url = build["download_url"] + status_json
        _fetch("status.json", url, status_json)
        build = json.load(open(status_json))

    print(json.dumps(build, indent=4))

    if retries == max_retries:
        print_red("Build is not finished on TuxSuite's side!")
        sys.exit(1)

    if "Build Timed Out" in build["status_message"]:
        print_red(build["status_message"])
        sys.exit(1)

    if build["status_message"] == "Unable to apply kernel patch":
        print_red(
            "Patch failed to apply to current kernel tree, does it need to be removed or updated?"
        )
        fetch_logs(build)
        sys.exit(1)

    return build


def fetch_logs(build):
    log = "build.log"
    url = build["download_url"] + log
    _fetch("logs", url, log)
    print(open(log).read())


def check_log(build):
    warnings_count = build["warnings_count"]
    errors_count = build["errors_count"]
    if warnings_count + errors_count > 0:
        print_yellow(f"{warnings_count} warnings, {errors_count} errors")
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
            print_yellow(f"Could not parse .config line '{line}'!?")
        configs[name] = state

    # Compare requested configs against the loaded dictionary.
    fail = False
    for config in build["kconfig"]:
        if 'CONFIG' not in config:
            continue
        name, state = config.split('=')
        # If a config is missing from the dictionary, it is considered 'n'.
        if state != configs.get(name, 'n'):
            print_red(f"FAIL: {config} not found in .config!")
            fail = True
        else:
            print(f"ok: {name}={state}")
    if fail:
        sys.exit(1)


def print_clang_info(build):
    # There is no point in printing the clang version information for anything
    # other than clang-nightly because the stable branches are very unlikely to
    # have regressions that require triage based on build date and revision
    # information
    if get_requested_llvm_version() != "clang-nightly":
        return

    metadata_file = "metadata.json"
    url = build["download_url"] + metadata_file
    _fetch(metadata_file, url, metadata_file)
    metadata_json = json.loads(open(metadata_file).read())
    print_yellow("Printing clang-nightly checkout date and hash")
    subprocess.run([
        "./scripts/parse-debian-clang.sh", "--print-info", "--version-string",
        metadata_json["compiler"]["version_full"]
    ])


def cwd():
    os.chdir(os.path.dirname(__file__))
    return os.getcwd()


def run_boot(build):
    cbl_arch = get_cbl_name()
    kernel_image = cwd() + "/" + get_image_name()
    if cbl_arch == "um":
        boot_cmd = ["./boot-utils/boot-uml.py"]
        # The execute bit needs to be set to avoid "Permission denied" errors
        os.chmod(kernel_image, 0o755)
    else:
        boot_cmd = ["./boot-utils/boot-qemu.py", "-a", cbl_arch]
    boot_cmd += ["-k", kernel_image]
    # If we are running a sanitizer build, we should increase the number of
    # cores and timeout because booting is much slower
    if "CONFIG_KASAN=y" in build["kconfig"] or \
       "CONFIG_KCSAN=y" in build["kconfig"] or \
       "CONFIG_UBSAN=y" in build["kconfig"]:
        boot_cmd += ["-s", "4"]
        if "CONFIG_KASAN=y" in build["kconfig"]:
            boot_cmd += ["-t", "20m"]
        else:
            boot_cmd += ["-t", "10m"]
        if "CONFIG_KASAN_KUNIT_TEST=y" in build["kconfig"] or \
           "CONFIG_KCSAN_KUNIT_TEST=y" in build["kconfig"]:
            print_yellow(
                "Disabling Oops problem matcher under Sanitizer KUnit build")
            print("::remove-matcher owner=linux-kernel-oopses::")

    # Before spawning a process with potentially different IO buffering,
    # flush the existing buffers so output is ordered correctly.
    sys.stdout.flush()
    sys.stderr.flush()

    try:
        subprocess.run(boot_cmd, check=True)
    except subprocess.CalledProcessError as e:
        if e.returncode == 124:
            print_red("Image failed to boot")
        raise e


def boot_test(build):
    if build["result"] == "unknown":
        print_red("unknown build result, skipping boot")
        sys.exit(1)
    if build["result"] == "fail":
        print_red("fatal build errors encountered during build, skipping boot")
        sys.exit(1)
    if "BOOT" in os.environ and os.environ["BOOT"] == "0":
        print_yellow("boot test disabled via config, skipping boot")
        return
    fetch_kernel_image(build)
    fetch_dtb(build)
    run_boot(build)


if __name__ == "__main__":
    missing = []
    for var in ["ARCH", "CONFIG", "LLVM_VERSION"]:
        if var not in os.environ:
            missing.append(var)
    if len(missing):
        for var in missing:
            print_red(f"${var} must be specified")
        show_builds()
        sys.exit(1)
    build = verify_build()
    print_yellow("Register clang error/warning problem matchers")
    for problem_matcher in glob.glob(".github/problem-matchers/*.json"):
        print(f"::add-matcher::{problem_matcher}")
    print_clang_info(build)
    check_log(build)
    check_built_config(build)
    boot_test(build)
