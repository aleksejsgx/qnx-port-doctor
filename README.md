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
