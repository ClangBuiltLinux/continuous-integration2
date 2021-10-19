#!/usr/bin/env bash

set -x

parse_parameters() {
    while [[ ${#} -gt 0 ]]; do
        case ${1} in
            -c | --check) action=check ;;
            -p | --print-info) action=print ;;
        esac
        shift
    done

    # Default action is check
    [[ -z ${action} ]] && action=check
}

parse_clang_version() {
    # The format of clang --version with apt.llvm.org builds looks like:
    # $ clang-14 --version
    # Debian clang version 14.0.0-++20210912100611+368af7558e55-1~exp1~20210912201415.4242
    # Target: x86_64-pc-linux-gnu
    # Thread model: posix
    # InstalledDir: /usr/local/bin
    clang_date=$(clang --version | head -n1 | cut -d + -f 3)
    clang_hash=$(clang --version | head -n1 | cut -d + -f 4 | cut -d - -f 1)

    # Next, we need to parse the date into a format the date binary can understand
    # We use bash substring expansion: https://wiki.bash-hackers.org/syntax/pe#substring_expansion
    clang_date="${clang_date:0:4}-${clang_date:4:2}-${clang_date:6:2} ${clang_date:8:2}:${clang_date:10:2}:${clang_date:12:2}"
}

check_action() {
    # Calculate the seconds between now and when Clang was built
    # 'date -u' ensures that we get an accurate measurement because clang's date is in UTC
    seconds_between=$(($(date -u +%s) - $(date -u -d "${clang_date:?}" +%s)))

    # Then convert that to days
    days_since=$((seconds_between / 86400))

    # Error out if days_since is greater than five days
    if [[ ${days_since} -ge 5 ]]; then
        set +x
        echo
        echo "clang hasn't been updated in ${days_since} days!"
        echo
        exit 1
    fi
}

print_action() {
    set +x
    echo
    echo "current date: $(date -u)"
    echo
    echo "clang checkout date: $(date -u -d "${clang_date:?}")"
    echo
    echo "clang revision: ${clang_hash}"
    echo
    echo "clang revision link: https://github.com/llvm/llvm-project/commit/${clang_hash}"
    echo
}

parse_parameters "${@}"
parse_clang_version
"${action}"_action
