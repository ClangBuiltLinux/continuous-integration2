#!/usr/bin/env python3
# pylint: disable=invalid-name

import os
from pathlib import Path
import sys

if 'GITHUB_ACTIONS' in os.environ:
    repo = Path(os.environ['GITHUB_WORKSPACE'])
else:
    repo = Path(__file__).resolve().parents[1]

workflows = Path(repo, '.github/workflows')

# Patches folder might not exist, which is okay, we will just have nothing to
# iterate over.
try:
    patch_folders = list(Path(repo, 'patches').iterdir())
except FileNotFoundError:
    patch_folders = []

for folder in patch_folders:
    # First, make sure that the patch folder is a valid tree (added patches
    # with the wrong tree name).
    if not list(workflows.glob(f"{folder.name}-*.yml")):
        print(f"{folder} does not have any corresponding workflow files?\n")
        print(
            '''The folder name should be the "name" field of the tree's definition in generator.yml.'''
        )
        sys.exit(1)

    # A single line shell command to update a particular series file
    update_series_command = f"\t$ ls -1 {folder}/*.patch | sed 's;{folder}/;;' > {folder}/series"

    # Next, make sure series file is not missing
    if not (series := Path(folder, 'series')).exists():
        print(f"{folder} exists but {series} doesn't?\n")
        print('Generate it with the following commands:\n')
        print(update_series_command)
        sys.exit(1)

    # Get contents of series file, as it will be used twice below
    series_text = series.read_text(encoding='utf-8')

    # Next, check that all of the patches in the series file exist (removed a
    # patch, did not update series file)
    for patch in series_text.splitlines():
        if not Path(folder, patch).exists():
            print(f"{patch} not found in {folder} but it is in {series}?\n")
            print('Update the series file:\n')
            print(update_series_command)
            sys.exit(1)

    # Finally, make sure that all of the patches in the patches folder are in
    # the series file (removed from series file, did not remove patch file)
    for patch in folder.glob('*.patch'):
        if patch.name not in series_text:
            print(
                f"{patch.name} not found in {series} but it is in {folder}?\n")
            print('Update the series file:\n')
            print(update_series_command)
            sys.exit(1)

for workflow in workflows.glob('*-clang-*.yml'):
    # Some trees contain dashes so this cannot be a simple '[0]'
    tree = '-'.join(workflow.name.split('-')[0:-2])

    wf_has_ps_opt = '--patch-series' in workflow.read_text(encoding='utf-8')
    patch_folder = Path(repo, 'patches', tree)

    if wf_has_ps_opt and not patch_folder.exists():
        print(
            f"{patch_folder} does not exist but '--patch-series' found in {workflow}?\n"
        )
        print('Regenerate the TuxSuite and workflow files:\n')
        print(f"\t$ ./generate.py {tree}")
        sys.exit(1)

    if patch_folder.exists() and not wf_has_ps_opt:
        print(
            f"{patch_folder} exists but '--patch-series' not found in {workflow}?\n"
        )
        print('Regenerate the TuxSuite and workflow files:\n')
        print(f"\t$ ./generate.py {tree}\n")
        print('or remove the patches if they are no longer being used.')
        sys.exit(1)

print('All patch file checks pass!')
