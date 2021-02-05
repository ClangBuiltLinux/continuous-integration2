#!/usr/bin/env bash

CI=$(dirname "$(readlink -f "${0}")")
cd "${CI}" || exit ${?}

BRANCHES=()
while ((${#})); do
    case ${1} in
        all) for FILE in tuxsuite/*.tux.yml; do BRANCHES+=("$(basename "${FILE//.tux.yml/}")"); done ;;
        *) BRANCHES+=("${1}") ;;
    esac
    shift
done

set -eux

for BRANCH in "${BRANCHES[@]}"; do
    ./generate_tuxsuite.py <generator.yml "${BRANCH}" >tuxsuite/"${BRANCH}".tux.yml
    ./generate_workflow.py <generator.yml "${BRANCH}" >.github/workflows/"${BRANCH}".yml
done
