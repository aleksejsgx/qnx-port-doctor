# qnx-port-doctor

Scan a C/C++ project for QNX portability blockers (epoll, inotify, prctl, eventfd, glibc-isms,
`-lrt/-ldl`, Linux `/proc` and sysfs paths, ...), get suggested QNX equivalents, and cross-build
with QNX SDP 8.0.

```sh
pip install -e .
qnx-port-doctor scan path/to/project              # text
qnx-port-doctor scan path -f md -o report.md      # markdown
qnx-port-doctor scan path -f json --fail-on never # json, CI friendly
qnx-port-doctor rules
source ~/qnx800/qnxsdp-env.sh
qnx-port-doctor build hello.c --arch x86_64       # qcc single file / make / cmake
qnx-port-doctor toolchain --arch aarch64le -o qnx.cmake
```

License: MIT

## Running on QNX (QEMU)

```sh
qnx-port-doctor run ./build-qnx/hello                    # boots the quickstart image, copies, runs
qnx-port-doctor run --keep --stdin input.json ./jq -- -c .  # keep VM up for faster re-runs
```

Defaults: image `~/qnx800/images/qemu/qemu`, ssh port 2222, user `qnxuser`
(password from `--password` or `QPD_PASSWORD`).

## False-positive reduction

Findings are downgraded to `info` (with a note) when the code is already conditional:
`#ifdef __linux__`, `#if HAVE_*`/`USE_*` feature guards, files compiled only under an
Automake `if HAVE_X` or a CMake Linux branch, and per-platform files such as `osdep-linux.c`.
