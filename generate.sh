#!/usr/bin/env bash

CI=$(dirname "$(readlink -f "${0}")")
cd "${CI}" || exit ${?}

# Ensure that LLVM_TOT_VERSION is up to date
curl -LSs https://raw.githubusercontent.com/llvm/llvm-project/main/llvm/CMakeLists.txt | grep -Fs "set(LLVM_VERSION_MAJOR" | cut -d ' ' -f 4 | sed 's/)//' >LLVM_TOT_VERSION

BRANCHES=()
while ((${#})); do
    case ${1} in
        -c | --check) CHECK=true ;;
        all) for FILE in tuxsuite/*.tux.yml; do BRANCHES+=("$(basename "${FILE//.tux.yml/}")"); done ;;
        *) BRANCHES+=("${1}") ;;
    esac
    shift
done

set -eux

for BRANCH in "${BRANCHES[@]}"; do
    ./generate_tuxsuite.py "${BRANCH}"
    ./generate_workflow.py "${BRANCH}"
done

if ${CHECK:=false}; then
    if ! git rev-parse --git-dir &>/dev/null; then
        set +x
        echo "Script is not being run inside a git repository!"
        exit 1
    fi

    if [[ -n "$(git --no-optional-locks status -uno --porcelain 2>/dev/null)" ]]; then
        set +x
        echo
        echo "Running 'generate.sh all' generated the following diff:"
        echo
        git diff HEAD
        echo
        echo "Please run 'generate.sh all' locally and commit then push the changes it creates!"
        exit 1
    fi
fi
