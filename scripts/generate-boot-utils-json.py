#!/usr/bin/env python3
# pylint: disable=invalid-name

from argparse import ArgumentParser
import os
from pathlib import Path
import subprocess

if 'GITHUB_ACTIONS' in os.environ:
    repo = Path(os.environ['GITHUB_WORKSPACE'])
else:
    repo = Path(__file__).resolve().parents[1]

parser = ArgumentParser(
    description='Download latest boot-utils release JSON from GitHub API')
parser.add_argument('github_token', help='Value of GITHUB_TOKEN')
args = parser.parse_args()

curl_cmd = [
    'curl', '--header', 'Accept: application/vnd.github+json', '--header',
    f"Authorization: Bearer {args.github_token}", '--output',
    Path(repo, 'boot-utils.json'), '--silent', '--show-error',
    'https://api.github.com/repos/ClangBuiltLinux/boot-utils/releases/latest'
]
subprocess.run(curl_cmd, check=True)
