#!/usr/bin/env python3
# pylint: disable=invalid-name

from collections import defaultdict
import datetime
from pathlib import Path
import sys

import croniter

# Add the root of the repo to PYTHONPATH for utils
ci_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ci_root))
# pylint: disable-next=wrong-import-position
from utils import get_config_from_generator  # noqa: E402

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

print(
    f"Total builds per week: {sum(item['total'] for item in builds_per_tree.values())}"
)

for item in sorted(builds_per_tree.items(),
                   key=lambda x: x[1]['total'],
                   reverse=True):
    tree = item[0]
    builds = item[1]

    print(f"\n  - tree: {tree}")
    print(f"    total: {builds['total']}")
    print('    breakdown:')
    del builds['total']
    for k, v in builds.items():
        print(f"    - clang-{k}: {v}")
