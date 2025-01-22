#!/usr/bin/env python3
# pylint: disable=invalid-name

from argparse import ArgumentParser
from pathlib import Path
import os
import subprocess
import sys
from tempfile import TemporaryDirectory

parser = ArgumentParser(
    description='Check that patches apply to their tree before running CI')
parser.add_argument(
    '-p',
    '--patches-dir',
    help='Path to patches directory (can be relative or absolute)',
    required=True,
    type=Path)
parser.add_argument('-r',
                    '--repo',
                    help='URL to git repository',
                    required=True)
parser.add_argument('-R',
                    '--ref',
                    help='Git reference to apply patches upon',
                    required=True)
args = parser.parse_args()

# If patches directory does not exist, there is nothing to check
if not (patches_dir := args.patches_dir.resolve()).exists():
    print(f"{patches_dir} does not exist, exiting 0...")
    sys.exit(0)

# There should be patches in there due to check-patches.py but we should double
# check and fail if not
if not list(patches_dir.glob('*.patch')):
    print(f"{patches_dir} does not contain any patches?")
    sys.exit(1)

# Rather that invoke 'git clone', which can be expensive for servers depending
# on the frequency and duration of requests, we fetch a tarball and 'git init'
# that.
with TemporaryDirectory() as workdir:
    # Fetch the tarball from the repository. This is different for each type of
    # tree that we support.
    if args.repo.startswith(
            'https://git.kernel.org/pub/scm/linux/kernel/git/'):
        # https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git -> 'linux'
        if (base_repo := args.repo.rsplit('/', 1)[1]).endswith('.git'):
            base_repo = base_repo[:-len('.git')]

        # https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git ->
        # https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/snapshot/linux-master.tar.gz
        tarball_url = f"{args.repo}/snapshot/{base_repo}-{args.ref}.tar.gz"
        strip = 1
    elif 'googlesource.com' in args.repo:
        tarball_url = f"{args.repo}/+archive/refs/heads/{args.ref}.tar.gz"
        strip = 0
    else:
        raise RuntimeError(f"Do not know how to download {args.repo}?")

    try:
        print(f"Downloading {tarball_url}...")
        tarball = subprocess.run(['curl', '-LSs', tarball_url],
                                 capture_output=True,
                                 check=True).stdout

        print(f"Extracting {tarball_url}...")
        subprocess.run(
            ['tar', '-C', workdir, f"--strip-components={strip}", '-xzf-'],
            check=True,
            input=tarball)
    except subprocess.CalledProcessError:
        print(
            'Downloading or extracting tarball failed! As this may be flakiness on the server end, exiting 0 to have TuxSuite fail later...'
        )
        sys.exit(0)

    # Ensure that we can always commit regardless of whether user.name or
    # user.email are set in whatever environment we are running in, as this is
    # a temporary tree.
    git_name = 'check-patch-apply.py'
    git_email = f"{git_name}@{os.uname().nodename}.local"
    git_commit_env_vars = {
        **os.environ,   # clone the environment, as subprocess may need it
        'GIT_AUTHOR_NAME': git_name,
        'GIT_AUTHOR_EMAIL': git_email,
        'GIT_COMMITTER_NAME': git_name,
        'GIT_COMMITTER_EMAIL': git_email,
    }  # yapf: disable

    print(f"Creating initial git repository in {workdir}...")
    subprocess.run(['git', 'init', '-q'], check=True, cwd=workdir)

    print(f"Adding files in {workdir}...")
    subprocess.run(['git', 'add', '.'], check=True, cwd=workdir)

    print(
        f"Creating initial commit '{args.repo} @ {args.ref}' in {workdir}...")
    subprocess.run(['git', 'commit', '-m', f"{args.repo} @ {args.ref}", '-q'],
                   check=True,
                   cwd=workdir,
                   env=git_commit_env_vars)

    print(f"Applying patches in {workdir}...")
    subprocess.run(['git', 'quiltimport', '--patches', patches_dir],
                   check=True,
                   cwd=workdir,
                   env=git_commit_env_vars)
