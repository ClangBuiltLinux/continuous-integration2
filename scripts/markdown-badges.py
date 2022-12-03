#!/usr/bin/env python3
import os, glob, re
from pkg_resources import parse_version

# Figure out where we to find the workflow definitions.
ci_root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


# Construct the markdown for a specific workflow badge.
def svg(workflow):
    if workflow == None:
        return "   "
    workflow_url = f"https://github.com/clangbuiltlinux/continuous-integration2/actions/workflows/{workflow}.yml"
    return f"[![{workflow} build status]({workflow_url}/badge.svg)]({workflow_url})"


print("Copy and paste the output below into README.md:\n")

# Be able to location and extract the name of a workflow.
name_re = re.compile(r'^name: (.*) \(([^\)]+)\)$')
# Quick "basename $arg .yml" regular expression.
base_re = re.compile(r'^.*/([^/]+)\.yml$')

# Find all the tuxsuite workflows.
trees = dict()
for yml in glob.glob(f"{ci_root}/.github/workflows/*.yml"):
    tuxsuite = False
    tree = None
    compiler = None
    for line in open(yml):
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
    if tree == None or compiler == None:
        raise ValueError(f"{yml}: missing 'name:'")

    m = base_re.search(yml)
    base = m.group(1)
    trees.setdefault(tree, dict())
    trees[tree][compiler] = base

# Construct the list of all compilers seen by any tree.
compilers = set()
for tree in trees:
    compilers.update(trees[tree].keys())
# Sort the columns with latest Clang on the left.
columns = sorted(compilers, key=parse_version, reverse=True)

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
rows = sorted(trees, key=parse_version, reverse=True)
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
workflow_url = 'https://github.com/clangbuiltlinux/continuous-integration2/actions/workflows/clang-version.yml'
print(f"\n[![Check clang version]({workflow_url}/badge.svg)]({workflow_url})")
