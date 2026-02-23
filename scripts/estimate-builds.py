#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "croniter>=6.0.0",
#     "pyyaml>=6.0.3",
# ]
# ///

# pylint: disable=invalid-name

from collections import defaultdict
import datetime

import croniter

from utils import get_config_from_generator

config = get_config_from_generator()

now = datetime.datetime.now(tz=datetime.timezone.utc)
week_from_now = now + datetime.timedelta(weeks=1)

builds_per_tree = defaultdict(lambda: defaultdict(lambda: 0))
for tree in config['tree_schedules']:
    tree_name = tree['name']
    tree_llvm_ver = tree['llvm_version']

    # Calculate the number of times that a workflow runs in a week based on its
    # schedule
    num_runs = len(
        list(croniter.croniter_range(now, week_from_now, tree['schedule'])))
    for build in config['builds']:
        if tree['git_repo'] == build['git_repo'] and \
           tree['git_ref'] == build['git_ref'] and \
           tree_llvm_ver == build['llvm_version']:
            builds_per_tree[tree_name]['total'] += num_runs
            builds_per_tree[tree_name][tree_llvm_ver] += num_runs

total_builds = sum(item['total'] for item in builds_per_tree.values())
print(f"Total builds per week: {total_builds}")

# Sort the list of builds by total number of builds descending
for tree, builds in sorted(builds_per_tree.items(),
                           key=lambda x: x[1]['total'],
                           reverse=True):
    print(f"\n  - tree: {tree}")
    print(f"    total: {builds['total']}")
    print('    breakdown:')
    for clang_version, num_builds in builds.items():
        if clang_version != 'total':
            print(f"    - clang-{clang_version}: {num_builds}")
