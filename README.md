[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/next/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3A"next")
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/mainline/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3A"mainline")
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/5.15/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3A5.15)
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/5.10/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3A5.10)
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/5.4/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3A5.4)
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/4.19/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3A4.19)
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/4.14/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3A4.14)
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/4.9/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3A4.9)
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/4.4/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3A4.4)
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/android-mainline/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3Aandroid-mainline)
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/android13-5.10/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3Aandroid13-5.10)
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/android12-5.10/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3Aandroid12-5.10)
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/android12-5.4/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3Aandroid12-5.4)
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/android-4.19/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3Aandroid-4.19)
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/android-4.14/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3Aandroid-4.14)
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/android-4.9/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3Aandroid-4.9)
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/lto-cfi/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3Alto-cfi)
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/lto-cfi-tip/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3Alto-cfi-tip)
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/tip/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3Atip)
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/arm64/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3Aarm64)
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/arm64-fixes/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3Aarm64-fixes)


Testing using [TuxSuite](https://gitlab.com/Linaro/tuxsuite) to build the Linux
kernel with LLVM under CI.

All test parameters are encoded in `generator.yml`; new trees, architectures,
configs, etc. should be added there.

### Usage

The tuxsuite and github actions workflow configs should be updated when
`generator.yml` changes. Ex.
```sh
$ BRANCH=next
$ ./generate_tuxsuite.py $BRANCH < generator.yml > tuxsuite/$BRANCH.tux.yml
$ ./generate_workflow.py $BRANCH < generator.yml > .github/workflows/$BRANCH.yml
```

The `generate.sh` script will run this for you based on the trees that are fed
to it. Ex.

```
# Generate just next and mainline TuxSuite and GitHub Action workflows
$ ./generate.sh next mainline

# Regenerate all of the current TuxSuite and GitHub Action workflows
$ ./generate.sh all
```

The CI the child workflows run can be rerun locally via:
```sh
$ ARCH=arm CONFIG=defconfig LLVM_VERSION=[12|11] [BOOT=0] [INSTALL_DEPS=1] \
  ./check_logs.py
```

Where `ARCH` and `CONFIG` are canonical names from the Linux kernel sources,
but should be listed in `generator.yml`.  `LLVM_VERSION` is which version of
LLVM to test.  `BOOT=0` can be specified to skip the boot test (for instance,
when boot failure is expected). `INSTALL_DEPS=1` can be specified to install
the child workflow dependcies (mostly QEMU) which the github actions workers
need to do.

Requires that a
[TuxSuite secret token](https://gitlab.com/Linaro/tuxsuite#setup-config) is
configured.
