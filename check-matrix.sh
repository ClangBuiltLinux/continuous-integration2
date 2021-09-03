#!/usr/bin/env bash

if [[ -n ${GITHUB_ACTIONS} ]]; then
    repo=${GITHUB_WORKSPACE}
else
    repo=$(dirname "$(readlink -f "${0}")")
fi

for workflow in "${repo}"/.github/workflows/*.yml; do
    # Get number of jobs from workflow (kick_tuxsuite... and md5 names)
    jobs=$(grep -cP "  _|  kick" "${workflow}")
    workflow=$(basename "${workflow}")

    # If we did not find any jobs in the following format, it is not a TuxSuite
    # workflow and we don't care.
    [[ ${jobs} -eq 0 ]] && continue

    echo "${workflow} has $jobs jobs"
    if [[ ${jobs} -gt 256 ]]; then
        echo "${workflow} has more than 256 jobs, please reduce the number of jobs or split the matrix up."
        ret_code=1
    fi
done

exit ${ret_code:-0}
