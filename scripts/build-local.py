#!/usr/bin/env python3
# pylint: disable=invalid-name

from argparse import ArgumentParser
import copy
from pathlib import Path
import re
import signal
import shutil
import sys

import yaml

NORMAL = '\033[0m'
RED = '\033[01;31m'
GREEN = '\033[01;32m'
YELLOW = '\033[01;33m'


def interrupt_handler(_signum, _frame):
    """
    Allows script to exit immediately when Ctrl-C is pressed
    """
    sys.exit(130)


signal.signal(signal.SIGINT, interrupt_handler)

try:
    import tuxmake.build
except ModuleNotFoundError:
    print(
        'The tuxmake package is required to use this script but it could not be found!'
    )
    print(
        'Follow the "Installing TuxMake" section of https://tuxmake.org to install it.'
    )
    sys.exit(1)

tuxmake_dir = Path(__file__).resolve().parents[1].joinpath('tuxmake')
default_build_dir = Path(tuxmake_dir, 'build')
default_output_dir = Path(tuxmake_dir, 'output')

parser = ArgumentParser(
    description='Build TuxSuite YAML files locally using TuxMake')
parser.add_argument('-b',
                    '--build-dir',
                    default=default_build_dir,
                    help=f"Build folder (default: {default_build_dir})")
parser.add_argument('-c',
                    '--ccache',
                    action='store_true',
                    help='Use ccache if it is available')
parser.add_argument('-C',
                    '--directory',
                    help='Path to kernel source',
                    required=True)
parser.add_argument('-d',
                    '--debug',
                    action='store_true',
                    help='Show debugging messages')
parser.add_argument('-f',
                    '--files',
                    help='TuxSuite YAML files to build',
                    nargs='+',
                    required=True)
parser.add_argument('-j',
                    '--jobs',
                    help='Jobs to build (default: build all jobs)',
                    nargs='+')
parser.add_argument(
    '-o',
    '--output-dir',
    default=default_output_dir,
    help=f"Output folder for TuxMake files (default: {default_output_dir})")
parser.add_argument('-v',
                    '--verbose',
                    action='store_true',
                    help="Show tuxmake's output")
args = parser.parse_args()

if not (tree := Path(args.directory).resolve()).exists():
    raise FileNotFoundError(
        f"Requested tree ('{tree}'), derived from provided directory ('{args.directory}'), could not be found?"
    )

if shutil.which('podman'):
    runtime = 'podman'
elif shutil.which('docker'):
    runtime = 'docker'
else:
    runtime = None

wrapper = None
if args.ccache:
    if shutil.which('ccache'):
        wrapper = 'ccache'
    else:
        print(
            f"{YELLOW}ccache was requested but it is not installed, ignoring...{NORMAL}"
        )

# Combine all jobs into one object for easy iteration
jobs = {}
for file_str in args.files:
    with open(file_str, encoding='utf-8') as file:
        config = yaml.safe_load(file)

    for job in config['jobs']:
        name = job['name']
        if args.jobs and name not in args.jobs:
            # This can be noisy under normal circumstances so only show it if
            # debugging is enabled.
            if args.debug:
                jobs_join = "', '"
                print(
                    f"D: {Path(file_str).name}: Job '{name}' was not in requested jobs ('{jobs_join.join(args.jobs)}'), skipping..."
                )
            continue

        builds = job['builds']
        if name in jobs:
            jobs[name] += builds
        else:
            jobs[name] = copy.deepcopy(builds)

build_dir = Path(args.build_dir).resolve()
output_dir = Path(args.output_dir).resolve()
for name, builds in jobs.items():
    print(f"I: Executing job '{name}' in {tree}")
    for build in builds:
        kconfig = build['kconfig']
        target_arch = build['target_arch']
        toolchain = build['toolchain']

        # If there is a dash in the toolchain, it means it is a versioned
        # toolchain in tuxmake terms, which requires a container runtime. If no
        # runtime was found in the user's current environment, let them know
        # immediately so that it can be corrected, versus tuxmake erroring out
        # and causing all the builds to appear to fail.
        if '-' in toolchain and not runtime:
            raise RuntimeError(
                f"tuxmake requires either podman or docker to use versioned toolchains ('{toolchain}') but neither could be found on your system!"
            )

        cfg_str = '+'.join(kconfig) if isinstance(kconfig, list) else kconfig
        print(f"I: Building {target_arch} {cfg_str} ({toolchain})... ",
              end='\n' if args.verbose else '',
              flush=True)

        if build_dir.exists():
            shutil.rmtree(build_dir)
        build_dir.mkdir(parents=True)

        # Replace the URL in the configuration string with a simple name, so
        # that it can be used in a path.
        if (match := re.search(r'(https://[^\+]+)', cfg_str)):
            url = match.groups()[0]
            if 'alpine' in url:
                distro = 'alpine'
            elif 'archlinux' in url:
                distro = 'archlinux'
            elif 'fedora' in url:
                distro = 'fedora'
            elif 'openSUSE' in url:
                distro = 'opensuse'
            cfg_str = cfg_str.replace(url, distro)
        specific_output_dir = Path(output_dir, toolchain, target_arch, cfg_str)
        specific_output_dir.mkdir(exist_ok=True, parents=True)

        # If kconfig is a list, we need to split it into 'kconfig' and
        # 'kconfig_add', as that is what tuxmake expects (I assume tuxsuite
        # does this internally).
        if isinstance(kconfig, list):
            build['kconfig_add'] = build['kconfig'][1:]
            build['kconfig'] = build['kconfig'][0]

        # Perform the build and report the result
        result = tuxmake.build.build(build_dir=build_dir,
                                     output_dir=specific_output_dir,
                                     quiet=(not args.verbose),
                                     runtime=runtime,
                                     tree=tree,
                                     wrapper=wrapper,
                                     **build)

        if all(info.passed for info in result.status.values()):
            print(f"{GREEN}PASS{NORMAL}")
        else:
            print(
                f"{RED}FAIL{NORMAL} (log available at {specific_output_dir}/build.log)"
            )

print(f"Artifacts are available at: {output_dir}")
