#!/usr/bin/env bash

CI=$(dirname "$(readlink -f "${0}")")

set -eu

cd "${CI}"

while ((${#})); do
    ./generate_tuxsuite.py <generator.yml "${1}" >tuxsuite/"${1}".tux.yml
    ./generate_workflow.py <generator.yml "${1}" >.github/workflows/"${1}".yml
    shift
done
