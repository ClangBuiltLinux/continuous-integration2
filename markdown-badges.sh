#!/usr/bin/env bash

ci_root=$(dirname "$0")

echo "Copy and paste the output below into README.md:"
echo

for workflow in "$ci_root"/.github/workflows/*.yml; do
    # We only care about TuxSuite workflows
    grep -q tuxsuite "$workflow" || continue

    workflow_name=$(basename "$workflow" | sed 's/.yml//')
    echo "[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/$workflow_name/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3A$workflow_name)"
done
