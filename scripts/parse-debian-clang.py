#!/usr/bin/env python3
# pylint: disable=invalid-name

from argparse import ArgumentParser
import datetime
import re
import subprocess

parser = ArgumentParser(description="Parse Debian's clang version")
parser.add_argument('-c',
                    '--check',
                    action='store_true',
                    help='Fail if clang has not been updated in 5 days')
parser.add_argument('-p',
                    '--print-info',
                    action='store_true',
                    help='Print information about clang version')
parser.add_argument(
    '-v',
    '--version-string',
    help="Use value as clang version instead of calling 'clang --version'")
args = parser.parse_args()

if not (version_string := args.version_string):
    clang_version = subprocess.run(['clang', '--version'],
                                   capture_output=True,
                                   check=True,
                                   text=True).stdout
    version_string = clang_version.splitlines()[0]

# $ clang-14 --version | head -1
# Debian clang version 14.0.0-++20210912100611+368af7558e55-1~exp1~20210912201415.4242
# This will get us the checkout date and the hash
clang_regex = r'\+\+([0-9]+)\+([a-z0-9]+)-'
if not (match := re.search(clang_regex, version_string)):
    raise RuntimeError('date and hash could not be found?')
clang_date, clang_hash = match.groups()

# Convert clang date string into a datetime object for easy calculations
clang_utc = datetime.datetime.strptime(clang_date + '+0000', '%Y%m%d%H%M%S%z')
now_utc = datetime.datetime.now(datetime.timezone.utc)
delta = now_utc - clang_utc

if args.print_info:
    print(
        f"clang checkout date: {clang_utc.strftime('%Y-%m-%d %H:%M %Z')} ({delta} ago)"
    )
    print(f"clang revision: {clang_hash}")
    print(
        f"clang revision link: https://github.com/llvm/llvm-project/commit/{clang_hash}"
    )

if args.check and delta.days >= 5:
    raise RuntimeError(f"Clang has not been updated for {delta}!")
