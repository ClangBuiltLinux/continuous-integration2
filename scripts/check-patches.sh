#!/usr/bin/env bash

if [[ -n ${GITHUB_ACTIONS} ]]; then
    repo=${GITHUB_WORKSPACE}
else
    repo=$(dirname "$(dirname "$(readlink -f "${0}")")")
fi

function update_series_commands() {
    echo
    echo "$ ls -1 ${folder}/*.patch | sed \"s;${folder}/;;\" > ${folder}/series"
}

for folder in "${repo}"/patches/*; do
    series=${folder}/series

    # First, make sure series file is not missing
    if [[ ! -f ${series} ]]; then
        echo "${folder} exists but ${series} doesn't?"
        echo
        echo "Generate it with the following commands:"
        update_series_commands
        exit 1
    fi

    # Next, check that all of the patches in the series file exist (removed a
    # patch, did not update series file)
    while IFS= read -r patch; do
        if [[ ! -f ${folder}/${patch} ]]; then
            echo "${folder} does not contain ${patch} but it is in ${series}?"
            echo
            echo "Update the series file:"
            update_series_commands
            exit 1
        fi
    done <"${series}"

    # Lastly, make sure that all of the patches in the patches folder are in
    # the series file (removed from series file, did not remove patch file)
    for patch in "${folder}"/*.patch; do
        patch=$(basename "${patch}")
        if ! grep -q "${patch}" "${series}"; then
            echo "${series} contains ${patch} but it does not exist in ${folder}?"
            echo
            echo "Update the series file:"
            update_series_commands
            exit 1
        fi
    done

done

for workflow in "${repo}"/.github/workflows/*.yml; do
    tree=$(basename "${workflow}" | sed 's/-clang-.*.yml//')
    patches=${repo}/patches/${tree}

    # Check for '--patch-series' and no patches (removed patches, did not
    # regenerate)
    if grep -q -- "--patch-series" "${workflow}" && [[ ! -d ${patches} ]]; then
        echo "${patches} does not exist but '--patch-series' present in ${workflow}?"
        echo
        echo "Regenerate the TuxSuite and workflow files:"
        echo
        echo "$ scripts/generate.sh ${tree}"
        exit 1
    fi

    # Check for patches and no '--patch-series' (added patches, did not
    # regenerate)
    if ! grep -q -- "--patch-series" "${workflow}" && [[ -d ${patches} ]]; then
        echo "${patches} exists but '--patch-series' not present in ${workflow}?"
        echo
        echo "Regenerate the TuxSuite and workflow files:"
        echo
        echo "$ scripts/generate.sh ${tree}"
        echo
        echo "or remove the patches if they are no longer being used."
        exit 1
    fi
done

echo "All patch file checks pass!"
exit 0
