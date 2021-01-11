#!/usr/bin/env bash

CI=$(dirname "$(readlink -f "${0}")")

set -eu

cd "${CI}"

while ((${#})); do
    ./generate_tuxbuild.py <generator.yml "${1}" >tuxbuild/"${1}".tux.yml
    ./generate_workflow.py <generator.yml "${1}" >.github/workflows/"${1}".yml
    shift
done
