# ClangBuiltLinux continuous-integration2 maintainer's guide

## Overview

At a high level, there are a number of YAML configuration files that compactly describe a great number of Linux kernel builds, which are consumed by generator Python scripts to automatically generate a number of TuxSuite build and GitHub Action workflow files. The basic pipeline of a GitHub Actions workflow:

- Check if the result of the previous build is expected to be the same due to the same Linux kernel source version and compiler version as the previous build.
- Run `tuxsuite` to build a series of Linux kernels according to a YAML file. `tuxsuite` generates a `builds.json` file that describes all the builds it did.
- Update the cache with the information from the current build (kernel source hash and compiler version).
- For each build that was done, spin up a job to check the build logs for problems and if requested, boot the kernel in QEMU. If the build failed or the kernel fails to boot, it is considered a fail.

## Repository layout and explanations

- `.github/`: Primarily contains GitHub Actions workflow files. The vast majority of these are automatically generated and should not be manually edited. The ones that are not automatically generated can be found with `ls .github/workflows | grep -v -- -clang-`.
	- `lint.yml` runs various checks to catch potential maintenance mistakes.
	- `clang-version.yml` checks TuxSuite's `clang-nightly` version to make sure that it is getting updated with the latest changes from `main`.
- `tuxsuite/`: TuxSuite YAML build files. These are all automatically generated and should never be manually edited.
- `generator/`:
	- `yml/`: The  YAML configuration files that ultimately describe all builds. A fuller explanation will follow in a section below.
	- `generate*.py`: Scripts that parse the `yml/*.yml` files and automatically generate majority of the `.github/workflow` files and all the `tuxsuite` files. When changing builds in any of the `*.yml`, `generate.py` should be run afterwards to ensure all generated files are updated.
- `caching/`: Frontend caching scripts that check the current build against the previous build to avoid doing builds where the result is expected to be the same.
- `utils.py`: Functions that may be used across all `*.py` scripts.
- `patches/`: Patch files that are applied before performing builds, allowing us to patch known failures with an upstream submitted patch (preferred) or a workaround until a proper solution can be performed. Patches should not accumulate, they should be burned down by chasing their submission/acceptance upstream.
- `scripts/`: Helper scripts to perform tasks in continuous integration such as linting or perform repetitive/mechanical tasks during maintenance. Each script has its own help text and options but a general overview:
	- `build-local.py`: Builds a `tuxsuite` YAML configuration on the developer's local build machine.
	- `check-matrix.py`: Ensures that a particular build matrix does not exceed GitHub's limit of 256 jobs.
	- `check-logs.py`: Inspects a particular build for errors/warnings and boots the kernel image in QEMU through `boot-utils` if requested.
	- `check-patches.py`: Ensures that all patch files in the `patches` folder are in the `series` file needed by `git quiltimport` and are properly associated with a tree based on the tree's name in the `trees` file.
	- `estimate-builds.py`: Estimates how many builds will be done a week because on the number of builds per tree and the build frequency.
	- `generate-boot-utils-json.py`: Generates a JSON file with the latest [`boot-utils`](https://github.com/ClangBuiltLinux/boot-utils) release information to minimize the number of GitHub API calls during boot testing.
	- `markdown-badges.py`: Generates the table in the README and [clangbuiltlinux.github.io](https://clangbuiltlinux.github.io) with all supported kernel and LLVM versions.
	- `parse-debian-clang.py`: Parses the Debian `clang` version to perform checks or print easy to consume information about it.

## Generator structure

The generator YAML files are designed to quickly and easily describe a large number of builds. There are a large number of trees and the supported LLVM version matrix grows with every release. The `generator/yml` directory contains:

- `llvm_versions`: Contains YAML anchors for the LLVM verisons that the matrix uses/supports. Most are of the form `llvm_#`, which denotes a version of LLVM that is not longer supported upstream by the LLVM community but is still considered supported by the kernel. There are two special anchors, `llvm_tot` and `llvm_latest`, which denote the current version of LLVM's `main` branch and the current version of LLVM's latest `release/` branch respectively. `llvm_tot` should always match the value in `LLVM_TOT_VERSION` (which gets automatically updated every time `generate.py` is run), as that will ensure that the `toolchain:` value of the tip of tree builds is always set to `clang-nightly`.
- `urls`: Contains anchors for the various URLs that are used throughout the generator. This includes links to the various Linux repositories that the matrix tests as well as external configurations (such as distribution ones).
- `schedules`: Contains anchors for the cron strings that are used in `trees` to build tree and compiler combinations at different rates. See [GitHub's `schedule` documentation](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule) for more information.
- `trees`: Contains anchors for the various trees that the matrix supports and the schedule of each tree and LLVM combination. An anchor in the `tree` section has three relevant values: A public, valid git repository URL, a git branch, and a CI internal short name that refers to that tree. An anchor in the `tree_schedules` uses the previously defined anchors to describe the version of LLVM being used, the tree being tested, and the frequency at which the combination should be tested. In general, trees and compilers that are more frequently updated will be tested more often than trees and compilers that are not updated as frequently (or at all).
- `architectures`: Contains anchors for each architecture that the matrix supports, which is provided to both `tuxsuite` and GitHub Actions to build and boot kernels properly.
- `targets`: Contains anchors for the various combinations of [`tuxmake` targets](https://gitlab.com/Linaro/tuxmake/-/blob/master/docs/targets.md?ref_type=heads) that the matrix uses. In general, `default` is used when boot testing is not required out of the particular configuration, such as `allmodconfig`, as this stops `tuxmake` (the backend for `tuxsuite`) from generating build artifacts that are not needed, slimming up our build times. `kernel` produces just a kernel image and `kernel_dtbs` products a kernel image and all of the device tree blobs associated with that particular build, which are necessary for boot for some configurations.
- `configs`: Contains anchors for all the various configurations that are tested. Each item should have at least a `config:` value, which can either be a single configuration target, a list that contains a configuration target and additional configurations that should be selected or fragments that should be merged in, or a URL of a configuration that will be fetched and built, and a `target:` value. See [TuxSuite's documentation]() for more information on what is supported. Some anchors have a `kernel_image:` value, which causes `tuxmake` to build and produce the requested image, which is usually because `boot-utils` expects to boot a particular image, which is different from the one that `tuxmake` produces by default.
- `tiers`: Contains anchors that describe the different "tiers" of LLVM support. `llvm_full` is preferred whenever possible but certain trees and compilers versions may dictate a different tier for a particular build in that case.
- `llvm-<ver>`: Contains the build descriptions for that particular version of LLVM. It is a combination of the anchors from `configs`, `trees`, `tiers`, a `boot:` boolean to indicate whether or not the configuration is bootable, and the corresponding LLVM version anchor from `llvm_version`. These files are written as if they are coalesced under a `builds:` section, which can be estimated with `echo builds: && cat *-llvm-*.yml`.

## Common maintenance tasks

### Adding new trees

Example: [Add chromeos-6.1 and chromeos-6.6](https://github.com/ClangBuiltLinux/continuous-integration2/pull/682)

- [ ] If necessary, add repository URL to `urls`
- [ ] Add anchor to `trees` with repository URL, branch to build, and a suitable internal tree name.
- [ ] Add anchors to `tree_schedules` with LLVM versions that the tree should be built with and a suitable schedule.
- [ ] Add builds to the various `*-llvm-*.yml` files (often, these will be copied and modified from existing trees).
- [ ] Commit current changes in a suitable commit structure.
- [ ] Run `generator/generate.py`.
- [ ] Commit generated changes as a separate commit.
- [ ] Run `scripts/markdown-badges.py` and update repository's `README.md` and [ClangBuiltLinux.github.io](https://github.com/ClangBuiltLinux/ClangBuiltLinux.github.io)'s `readme.md` with the results.

### Removing unsupported trees

Example: [drop 4.14](https://github.com/ClangBuiltLinux/continuous-integration2/pull/679)

- [ ] Drop anchors in `trees`/`tree_schedules`
- [ ] Drop builds from all relevant `*-llvm-*.yml` files
- [ ] Commit current changes in a suitable commit structure.
- [ ] Remove all generated build files: `rm .github/workflows/*-clang-*.yml tuxsuite/*-clang-*.yml`
- [ ] Run `generator/generate.py` and make sure that diff is just the removal of the relevant generated files.
- [ ] Commit generated changes as a separate commit.
- [ ] Run `scripts/markdown-badges.py` and update repository's `README.md` and [ClangBuiltLinux.github.io](https://github.com/ClangBuiltLinux/ClangBuiltLinux.github.io)'s `readme.md` with the results.

### Adding new builds

Example: [Add support for RISC-V LTO on -next](https://github.com/ClangBuiltLinux/continuous-integration2/pull/690)

- [ ] Add relevant anchors to `architectures`/`tiers` if necessary (rare).
- [ ] Add relevant anchors in `configs` if necessary.
- [ ] Add builds to the various `*-llvm-*.yml` for the compiler/tree combinations that need it.
- [ ] Commit current changes in a suitable commit structure.
- [ ] Run `generator/generate.py`.
- [ ] Commit generated changes as a separate commit.
