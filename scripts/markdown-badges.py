#!/usr/bin/env python3
# pylint: disable=invalid-name
import glob
import os
import re

from packaging.version import _BaseVersion


# Converts an item's position in an iterable to a ranking, which allows earlier
# items in an iterable to stay ahead of later items when compared.
def order_to_rank(iterable, item):
    return len(iterable) - iterable.index(item)


class ClangVersion(_BaseVersion):

    def __init__(self, version):
        if 'clang-' not in version:
            raise ValueError(f"Invalid clang version ('{version}') provided?")

        version = version.split('-', 1)[1]

        # Force 'clang-android' to be last
        self._key = 0 if version == 'android' else int(version)


class KernelVersion(_BaseVersion):

    def __init__(self, version):
        major = 0
        minor = 0
        patch = 0

        # The general categories for builds, in the order they should appear in
        # the matrix.
        categories = ['upstream', 'lts', 'maintainers', 'android']

        # Named upstream trees, which do not have a version associated with them
        upstream_trees = ('next', 'mainline', 'stable')
        if version in upstream_trees:
            category = 'upstream'
            major = order_to_rank(upstream_trees, version)

        # LTS releases
        if (match := re.search(r'^([\d|\.]+)$', version)):
            category = 'lts'
            major, minor = map(int, match.groups()[0].split('.'))

        # Named maintainer trees
        maintainer_trees = ('tip', )
        if version in maintainer_trees:
            category = 'maintainers'
            major = order_to_rank(maintainer_trees, version)

        # Android trees
        if 'android' in version:
            category = 'android'

            version = version.replace(category, '').split('-')

            # Ensure 'android-mainline' is at the top of the list
            if version[1] == 'mainline':
                major = 99
            else:
                major, minor = map(int, version[1].split('.'))
                # Set the patch level to the Android version so that
                # android14-5.15 is newer than android13-5.15.
                if version[0]:
                    patch = int(version[0])

        rank = order_to_rank(categories, category)

        self._key = (rank, major, minor, patch)


# Figure out where we to find the workflow definitions.
ci_root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


# Construct the markdown for a specific workflow badge.
def svg(workflow):
    if workflow is None:
        return "   "
    workflow_url = f"https://github.com/clangbuiltlinux/continuous-integration2/actions/workflows/{workflow}.yml"
    badge_url = f"https://kernel.outflux.net/cbl/badges/{workflow}.svg"
    return f"[![{workflow} build status]({badge_url})]({workflow_url})"


print("Copy and paste the output below into README.md:\n")

# Be able to location and extract the name of a workflow.
name_re = re.compile(r'^name: (.*) \(([^\)]+)\)$')
# Quick "basename $arg .yml" regular expression.
base_re = re.compile(r'^.*/([^/]+)\.yml$')

# Find all the tuxsuite workflows.
trees = {}
for yml in glob.glob(f"{ci_root}/.github/workflows/*.yml"):
    tuxsuite = False
    tree = None
    compiler = None
    with open(yml, encoding='utf-8') as file:
        for line in file:
            m = name_re.search(line)
            if m:
                tree = m.group(1)
                compiler = m.group(2)
                continue
            if 'tuxsuite' in line:
                tuxsuite = True
                break
    if not tuxsuite:
        continue
    # Found a tuxsuite workflow with no "name:" field?!
    if tree is None or compiler is None:
        raise ValueError(f"{yml}: missing 'name:'")

    m = base_re.search(yml)
    base = m.group(1)
    trees.setdefault(tree, {})
    trees[tree][compiler] = base

# Construct the list of all compilers seen by any tree.
compilers = set()
for _, tree in trees.items():
    compilers.update(tree.keys())
# Sort the columns with latest Clang on the left.
columns = sorted(compilers, key=ClangVersion, reverse=True)

# To stabilize the size of the the SVGs to make the table as presentable
# as possible, we must do our best to keep the table columns the same
# width. To that end, figure out the widest column name.
# Note that the SVGs themselves vary in size, but we can only do so much.
max_width = len(max(columns, key=len))

# - Make every column the same width
# - Force whitespace to non-breaking (to keep the cell from eliding spaces)
# - Replace "-" with non-breaking-dash (to keep the name from wrapping)
print("|     | " + " | ".join([
    "&nbsp;" * (max_width - len(col)) + col.replace('-', '&#8209;')
    for col in columns
]) + " |")
# Align tree name to the right for readability, and center the badges.
print("| ---: |" + " :---: |" * len(columns))

# Sort so latest trees are at the top.
rows = sorted(trees, key=KernelVersion, reverse=True)
# Manually override some trees to the top, since they're unversioned.
rows.remove('next')
rows.remove('mainline')
rows.insert(0, 'mainline')
rows.insert(0, 'next')

# Emit the svg markdown for each tree/compiler combo, if it exists.
for tree in rows:
    # Keep names from wrapping.
    row = tree.replace('-', '&#8209;')
    print(f"| {row} | " + " | ".join(
        [svg(trees[tree].get(compiler, None)) for compiler in columns]) + " |")

# Output a button for the "Check clang version" workflow, which ensures that
# tip of tree LLVM is being updating. This does not need to be a part of the
# table above.
cv_workflow_url = 'https://github.com/clangbuiltlinux/continuous-integration2/actions/workflows/clang-version.yml'
print(
    f"\n[![Check clang version]({cv_workflow_url}/badge.svg)]({cv_workflow_url})"
)
