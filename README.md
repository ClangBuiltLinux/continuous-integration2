[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/next/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3A"next")
[![Actions Status](https://github.com/clangbuiltlinux/continuous-integration2/workflows/mainline/badge.svg)](https://github.com/clangbuiltlinux/continuous-integration2/actions?query=workflow%3A"mainline")

Testing using [TuxBuild](https://gitlab.com/Linaro/tuxbuild) to build the Linux
kernel with LLVM under CI.

All test parameters are encoded in `generator.yml`; new trees, architectures,
configs, etc. should be added there.

### Usage

The tuxbuild and github actions workflow configs should be updated when
`generator.yml` changes. Ex.
```sh
$ BRANCH=next
$ ./generate_tuxbuild.py $BRANCH < generator.yml > $BRANCH.tux.yml
$ ./generate_workflow.py $BRANCH < generator.yml > .github/workflows/$BRANCH.yml
```

The CI the child workflows run can be rerun locally via:
```sh
$ ARCH=arm CONFIG=defconfig [BOOT=0] [INSTALL_DEPS=1] ./check_logs.py
```

Where `ARCH` and `CONFIG` are canonical names from the Linux kernel sources,
but should be listed in `generator.yml`. `BOOT=0` can be specified to skip the
boot test (for instance, when boot failure is expected). `INSTALL_DEPS=1` can
be specified to install the child workflow dependcies (mostly QEMU) which the
github actions workers need to do.

Requires that a
[TuxBuild secret token](https://gitlab.com/Linaro/tuxbuild#setup-config) is
configured.
