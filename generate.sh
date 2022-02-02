#!/usr/bin/env bash

CI=$(dirname "$(readlink -f "${0}")")
cd "${CI}" || exit ${?}

# Ensure that LLVM_TOT_VERSION is up to date
curl -LSs https://raw.githubusercontent.com/llvm/llvm-project/main/llvm/CMakeLists.txt | grep -Fs "set(LLVM_VERSION_MAJOR" | cut -d ' ' -f 4 | sed 's/)//' >LLVM_TOT_VERSION

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
