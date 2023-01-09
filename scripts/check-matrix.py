#!/usr/bin/env python3
# pylint: disable=invalid-name

import os
from pathlib import Path
import re
import sys

GH_LIMIT = 256

if 'GITHUB_ACTIONS' in os.environ:
    repo = Path(os.environ['GITHUB_WORKSPACE'])
else:
    repo = Path(__file__).resolve().parents[1]

# TuxSuite jobs either start with '_' or 'kick'
jobs_re = re.compile(r'^\s+(_|kick)', flags=re.M)

overlimit_workflows = {}
for workflow in sorted(Path(repo, '.github/workflows').glob('*.yml')):
    workflow_text = workflow.read_text(encoding='utf-8')
    # Number of jobs is the number of matches found
    if (jobs := len(jobs_re.findall(workflow_text))) > GH_LIMIT:
        overlimit_workflows[workflow.name] = jobs

if overlimit_workflows:
    print(
        f"The following workflows have more than {GH_LIMIT} jobs, please reduce the number of jobs or split the matrix up:\n"
    )
    # sys.exit() is called after printing all workflows so that all problematic
    # workflows are reported so they can be fixed all at once, rather than
    # piecemeal.
    for k, v in overlimit_workflows.items():
        print(f"{k} ({v})")
    sys.exit(1)
