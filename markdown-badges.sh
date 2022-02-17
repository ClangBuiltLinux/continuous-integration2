#!/usr/bin/env bash

ci_root=$(dirname "$0")

echo "Copy and paste the output below into README.md:"
echo

for workflow in "$ci_root"/.github/workflows/*.yml; do
    # We only care about TuxSuite workflows
    grep -q tuxsuite "$workflow" || continue

    workflow_url=https://github.com/clangbuiltlinux/continuous-integration2/actions/workflows/$(basename "$workflow")
    echo "[![Actions Status]($workflow_url/badge.svg)]($workflow_url)"
done
