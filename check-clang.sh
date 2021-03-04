#!/usr/bin/env bash

set -x

# The format of clang --version with apt.llvm.org builds looks like:
# $ clang-9 --version
# clang version 9.0.0-svn356030-1~exp1+0~20190313082415.405~1.gbp505100 (trunk)
# Target: x86_64-pc-linux-gnu
# Thread model: posix
# InstalledDir: /usr/bin
CLANG_DATE=$(clang --version | head -n1 | cut -d '~' -f 3 | cut -d . -f 1)

# Next, we need to parse the date into a format the date binary can understand
# We use bash substring expansion: https://wiki.bash-hackers.org/syntax/pe#substring_expansion
CLANG_DATE="${CLANG_DATE:0:4}-${CLANG_DATE:4:2}-${CLANG_DATE:6:2} ${CLANG_DATE:8:2}:${CLANG_DATE:10:2}:${CLANG_DATE:12:2}"

# Calculate the seconds between now and when Clang was built
# 'date -u' ensures that we get an accurate measurement because clang's date is in UTC
SECONDS_BETWEEN=$(($(date -u +%s) - $(date -u -d "${CLANG_DATE:?}" +%s)))

# Then convert that to days
DAYS_SINCE=$((SECONDS_BETWEEN / 86400))

# Error out if DAYS_SINCE is greater than five days
if [[ ${DAYS_SINCE} -ge 5 ]]; then
    set +x
    echo
    echo "clang hasn't been updated in ${DAYS_SINCE} days!"
    echo
    exit 1
fi
