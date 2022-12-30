#!/usr/bin/env python3

from argparse import ArgumentParser
import os
from pathlib import Path
import re
import subprocess
import sys

import generate_tuxsuite
import generate_workflow
import utils


def parse_args(trees):
    parser = ArgumentParser(
        description='Generate yml files and perform extra checks')

    parser.add_argument('-c',
                        '--check',
                        action='store_true',
                        help='Fail if generating yml files results in a diff')
    parser.add_argument(
        'trees',
        choices=trees + ['all'],
        default='all',
        help='The trees to generate yml files for (default: all)',
        metavar='TREES',
        nargs='*')

    return parser.parse_args()


def update_llvm_tot_version():
    # Avoids pulling in an extra Python package dependency
    curl_cmd = [
        'curl', '-fLSs',
        'https://raw.githubusercontent.com/llvm/llvm-project/main/llvm/CMakeLists.txt'
    ]
    cmakelists = subprocess.run(curl_cmd,
                                capture_output=True,
                                check=True,
                                text=True).stdout

    if not (match := re.search(r'set\(LLVM_VERSION_MAJOR (\d+)', cmakelists)):
        raise Exception('Could not find LLVM_VERSION_MAJOR?')
    if not (llvm_version_tot := Path('LLVM_TOT_VERSION')).exists():
        raise Exception('Not in the right folder?')
    llvm_version_tot.write_text(f"{match.group(1)}\n", encoding='utf-8')


def generate(config, tree):
    print(f"Generating TuxSuite and GitHub Actions files for {tree}...")
    for llvm_ver in utils.get_llvm_versions(config, tree):
        generate_tuxsuite.emit_tuxsuite_yml(config, tree, llvm_ver)
        generate_workflow.print_builds(config, tree, llvm_ver)


def check(trees_arg):
    try:
        subprocess.run(['git', 'rev-parse', '--git-dir'],
                       check=True,
                       capture_output=True)
    except subprocess.CalledProcessError:
        # Print a nicer error message versus spewing the exception
        print('Script is not being run inside a git repository!')
        sys.exit(1)

    if subprocess.run(
        ['git', '--no-optional-locks', 'status', '-uno', '--porcelain'],
            capture_output=True,
            check=True).stdout:
        print(
            f"\nRunning 'generate.py {trees_arg}' generated the following diff:\n",
            flush=True)
        subprocess.run(['git', '--no-pager', 'diff', 'HEAD'], check=True)
        print(
            "\nPlease run 'generate.py all' locally then commit and push the changes it creates!"
        )
        sys.exit(1)


if __name__ == '__main__':
    os.chdir(Path(__file__).resolve().parent)

    # The list of valid trees come from the input, so we parse the input, then
    # check command line flags.
    generated_config = utils.get_config_from_generator()
    all_trees = [tree['name'] for tree in generated_config['trees']]
    args = parse_args(all_trees)

    # Ensure that the LLVM_TOT_VERSION file is up to date
    update_llvm_tot_version()

    # If 'all' is found in trees, it overrides all other choices.
    for tree_name in all_trees if 'all' in args.trees else args.trees:
        generate(generated_config, tree_name)

    if args.check:
        check(args.trees)
