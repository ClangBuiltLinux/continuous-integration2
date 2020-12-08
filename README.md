[![Actions Status](https://github.com/nickdesaulniers/github_actions_playground/workflows/Clang%20Linux%20CI%20v2/badge.svg)](https://github.com/nickdesaulniers/github_actions_playground/actions)

Testing using [TuxBuild](https://gitlab.com/Linaro/tuxbuild) to build the Linux
kernel with LLVM under CI.

### Usage

```sh
$ ARCH=arm32_v7 [BOOT=0] ./check_logs.py
```

Where `ARCH` is one of:
* arm32_v5
* arm32_v6
* arm32_v7
* arm64
* mips
* ppc32
* ppc64
* ppc64le
* riscv
* s390
* x86
* x86_64

Requires that a
[TuxBuild secret token](https://gitlab.com/Linaro/tuxbuild#setup-config) is
configured.
