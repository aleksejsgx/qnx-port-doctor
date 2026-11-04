# Port your first open-source project to QNX 8 with qnx-port-doctor

| | |
|---|---|
| **Duration** | about 45 minutes |
| **You will port** | [jq](https://github.com/jqlang/jq) 1.8.1, then [tmux](https://github.com/tmux/tmux) 3.5a |
| **Target** | QNX SDP 8.0, x86_64, running on QEMU |
| **Level** | Comfortable with a shell and `./configure && make` |

## 1. Overview

Most open-source C code is written and tested on Linux. When you rebuild it for QNX,
the compiler stops at the first Linux assumption, you fix it, rebuild, hit the next one,
and repeat. `qnx-port-doctor` turns that loop into a checklist:

1. **scan** the tree and see every blocker up front, with a suggested QNX equivalent;
2. **fix** the mechanical ones with a patch you can review;
3. **build** with the right QNX host triple, libraries and flags;
4. **run** the result on a real QNX 8 kernel in QEMU.

What you will learn:

* the handful of QNX differences that break most ports (and why);
* how to read a portability report, and which findings you can ignore;
* how to cross-compile an autotools project for QNX;
* how to test a QNX binary without hardware.

## 2. Set up

You need:

* **QNX SDP 8.0** (free non-commercial licence from [qnx.com](https://www.qnx.com/products/everywhere/)),
  installed with the QNX Software Center, e.g. into `~/qnx800`;
* the **QEMU quickstart image** package (`com.qnx.qnx800.quickstart.qemu`), unpacked with its
  `unpack_qemu_image.sh` into `~/qnx800/images/qemu/qemu`;
* `qemu-system-x86_64`, Python 3.8+, `curl`, `patch`, `make`.

Install the tool and load the SDP environment:

```sh
git clone <your copy of qnx-port-doctor> && cd qnx-port-doctor
pip install -e .
source ~/qnx800/qnxsdp-env.sh
qcc -V 2>&1 | head -3          # sanity check: lists the gcc_nto* targets
```

> **Tip: check the image unpacked completely.** The quickstart disk is a ~50 GB sparse file.
> If your disk filled up during unpacking, QNX boots but reports
> `mount: Can't mount /data ... Corrupted file system`. Compare the size of
> `output/disk-qemu` with the sector count in `output/disk-qemu.vmdk` × 512.

Smoke-test the whole chain with hello world:

```sh
printf '#include <stdio.h>\nint main(void){puts("hello qnx");}\n' > hello.c
qnx-port-doctor build hello.c --out build-qnx
qnx-port-doctor run --keep build-qnx/hello
```

The first `run` boots QNX (about 30 seconds without KVM) and prints `hello qnx`.
`--keep` leaves the VM running, so the next runs take a second or two.

## 3. Get jq and scan it

```sh
mkdir -p ~/ports && cd ~/ports
curl -L https://github.com/jqlang/jq/releases/download/jq-1.8.1/jq-1.8.1.tar.gz | tar xz
qnx-port-doctor scan jq-1.8.1 --min-severity warning
```

Use a **release tarball**: it already contains `configure`, so you don't need autotools.

You will see something like:

```
src/builtin.c:2: error [QPD035] _XOPEN_SOURCE defined without a value
    # define _XOPEN_SOURCE
    fix: QNX <sys/platform.h> rejects it (#error ... XOPEN_SOURCE is not supported); use `#define _XOPEN_SOURCE 700`.
Makefile.am:93: warning [QPD060] glibc split library
    libinject_errors_la_LIBADD = -ldl
...
```

How to read this:

* **error**: the build will fail on QNX. Here, glibc accepts an empty `_XOPEN_SOURCE`,
  but QNX's headers require a version number (500, 600 or 700) and stop with `#error`.
* **warning**: probably a problem. `-ldl` here is only used by an optional
  error-injection test library, so it is safe to leave.
* **info**: something to know but usually harmless, often code that the project
  already compiles only on Linux. Use `--min-severity info` to see these and their notes.

## 4. Fix jq with a reviewable patch

```sh
qnx-port-doctor fix jq-1.8.1 -o jq-qnx.patch
cat jq-qnx.patch
```

```diff
# qnx-port-doctor: src/builtin.c: QPD035
--- a/src/builtin.c
+++ b/src/builtin.c
@@ -1,5 +1,5 @@
 #ifndef __sun__
-# define _XOPEN_SOURCE
+# define _XOPEN_SOURCE 700
 # define _XOPEN_SOURCE_EXTENDED 1
```

The patch is a normal unified diff, so you can review it, commit it, or send it upstream.
Apply it:

```sh
cd jq-1.8.1 && patch -p1 < ../jq-qnx.patch && cd ..
```

(`qnx-port-doctor fix --apply` edits the files directly if you prefer.)

## 5. Cross-build jq

```sh
qnx-port-doctor build jq-1.8.1 --autotools \
  --configure-arg=--without-oniguruma --configure-arg=--disable-docs \
  --configure-arg=--disable-shared
```

`--autotools` prints what it is doing, then runs it:

```
+ export CC='qcc -Vgcc_ntox86_64'
+ export LIBS='-lsocket -lregex -lm'
+ export CPPFLAGS='-include .../qnx_compat.h'
+ ./configure --host=x86_64-pc-nto-qnx8.0.0 ...
+ make -j8
```

Things to notice:

* `--host=x86_64-pc-nto-qnx8.0.0` tells configure it is cross-compiling for QNX
  (`--arch aarch64le` for Arm targets);
* QNX keeps BSD sockets in **libsocket** and POSIX regex in **libregex**, not in libc, so
  they are always added to `LIBS`;
* `qnx_compat.h` is a small header with safe fallbacks for common QNX gaps. We don't need it
  for jq, so you can add `--no-compat` to prove that the patch alone is enough.

> **If make fails with `src/builtin.inc: No such file`**, run `make -C jq-1.8.1 src/builtin.inc`
> once and build again. This is a jq parallel-make race, not a QNX issue.

## 6. Run jq on QNX

```sh
echo '{"board":"qemu","os":{"name":"QNX","version":8}}' > in.json
qnx-port-doctor run --keep --stdin in.json jq-1.8.1/jq -- -c '.os'
# {"name":"QNX","version":8}
```

Now run jq's own test suite inside QNX:

```sh
qnx-port-doctor run --stdin jq-1.8.1/tests/jq.test jq-1.8.1/jq -- --run-tests | tail -1
# 509 of 522 tests passed (9 malformed, 0 skipped)
```

Most failures are module tests: they need the `tests/modules` directory, which we didn't
copy (`--file` copies single files). One failure is a real QNX difference:
`strptime("%FT%T")`. QNX's `strptime` doesn't support the GNU shorthands `%F`, `%T`, `%D`
and `%R`. When a C program passes these formats as literals, rule QPD037 flags them and
`fix` rewrites them to `%Y-%m-%d` and `%H:%M:%S`. In jq the format comes from the user's
script at runtime, so the scanner can only point at the call (QPD038, info).

**Checkpoint:** you have ported jq to QNX 8 with a one-line patch and checked it against its own test suite.

## 7. A bigger port: tmux

tmux depends on **libevent** and **ncurses**. ncurses comes with the SDP; libevent we build
ourselves into a small sysroot.

### 7.1 libevent

```sh
export SYSROOT=~/ports/sysroot
curl -L https://github.com/libevent/libevent/releases/download/release-2.1.12-stable/libevent-2.1.12-stable.tar.gz | tar xz
qnx-port-doctor scan libevent-2.1.12-stable --min-severity warning
```

libevent has epoll, eventfd and sendfile code, but you won't see those as errors. They sit
behind `#ifdef EVENT__HAVE_EPOLL`-style guards or in files that the build only compiles
on Linux, so the scanner reports them as `info` with a note such as
`guarded by EVENT__HAVE_SYS_SENDFILE_H`. What remains is a real QNX issue:

```
signal.c:257: warning [QPD039] SA_RESTART not supported on QNX 8
```

QNX 8's `<signal.h>` lists `SA_RESTART` as "not supported yet", so the flag doesn't exist.
Without it, an interrupted system call returns `EINTR` instead of restarting. libevent
already handles `EINTR`, so a fallback of `0` is safe:

```sh
qnx-port-doctor fix libevent-2.1.12-stable -o libevent.patch && cat libevent.patch
```

```diff
+/* QNX 8 does not provide SA_RESTART; interrupted calls return EINTR. */
+#ifndef SA_RESTART
+#define SA_RESTART 0
+#endif
```

```sh
(cd libevent-2.1.12-stable && patch -p1 < ../libevent.patch)
qnx-port-doctor build libevent-2.1.12-stable --autotools --prefix $SYSROOT \
  --configure-arg=--disable-shared --configure-arg=--disable-openssl \
  --configure-arg=--disable-samples --configure-arg=--disable-libevent-regress
make -C libevent-2.1.12-stable install
```

### 7.2 tmux

```sh
curl -L https://github.com/tmux/tmux/releases/download/3.5a/tmux-3.5a.tar.gz | tar xz
qnx-port-doctor scan tmux-3.5a --min-severity warning
```

```
client.c:561: warning [QPD039] SA_RESTART not supported on QNX 8
proc.c:241:   warning [QPD039] SA_RESTART not supported on QNX 8
compat/imsg-buffer.c:551: warning [QPD044] IOV_MAX is not a compile-time constant on QNX
...
```

tmux has Linux-only code too: a `prctl(PR_SET_NAME)` call, Linux session keyrings, and
`osdep-linux.c`. All of it is downgraded to `info`, because tmux only compiles it under
`HAVE_PRCTL`, `if HAVE_KEYCTL`, or as the Linux platform file. That leaves eight warnings,
and they are exactly the lines a QNX build fails on:

* `SA_RESTART`, as in libevent;
* `IOV_MAX`: POSIX allows `<limits.h>` to leave it undefined when the limit is only
  known at runtime, and QNX does exactly that (`sysconf(_SC_IOV_MAX)`). The fix falls back
  to `UIO_MAXIOV` from `<sys/uio.h>`.

```sh
qnx-port-doctor fix tmux-3.5a -o tmux.patch     # 3 files: client.c, proc.c, compat/imsg-buffer.c
(cd tmux-3.5a && patch -p1 < ../tmux.patch)
qnx-port-doctor scan tmux-3.5a --fail-on warning && echo "no blockers left"

qnx-port-doctor build tmux-3.5a --autotools --no-compat --prefix $SYSROOT \
  --lib=-levent_core --lib=-lncurses \
  --env "LIBNCURSES_CFLAGS= " --env LIBNCURSES_LIBS=-lncurses
```

The `LIBNCURSES_*` variables skip tmux's pkg-config lookup for ncurses: the SDP ships
the library and headers but no `.pc` file.

### 7.3 Run tmux headless on QNX

tmux is interactive, but it also has a full command-line client. That makes it easy to
script a smoke test (`examples/tmux-smoke.sh`):

```sh
#!/bin/sh
cd /tmp/qpd; chmod +x tmux; export TERM=xterm
./tmux -V
./tmux -S /tmp/qpd/sock -f /dev/null new-session -d -s qnx -x 80 -y 24 \
  'echo hello-from-tmux-on-qnx; uname -sr; sleep 30'
sleep 2
./tmux -S /tmp/qpd/sock capture-pane -p -t qnx | grep -v '^$'
./tmux -S /tmp/qpd/sock split-window -t qnx 'sleep 30'
./tmux -S /tmp/qpd/sock list-panes -t qnx
./tmux -S /tmp/qpd/sock kill-server
```

```sh
qnx-port-doctor run --file tmux-3.5a/tmux examples/tmux-smoke.sh
```

```
tmux 3.5a
hello-from-tmux-on-qnx
QNX 8.0.0
0: [80x12] [history 0/2000, 780 bytes] %0
1: [80x11] [history 0/2000, 440 bytes] %1 (active)
```

A tmux server, its client and a pseudo-terminal pair, all running on QNX 8. 🎉

## 8. Bonus: the same port on 64-bit Arm (aarch64le)

Everything above also targets Arm. Rebuild with `--arch aarch64le`:

```sh
mkdir a64 && tar -C a64 -xzf jq-1.8.1.tar.gz
qnx-port-doctor fix a64/jq-1.8.1 --apply
qnx-port-doctor build a64/jq-1.8.1 --autotools --arch aarch64le \
  --configure-arg=--without-oniguruma --configure-arg=--disable-docs --configure-arg=--disable-shared
qnx-port-doctor build cJSON-1.7.18 --arch aarch64le --out cjson-a64 \
  --configure-arg=-DBUILD_SHARED_LIBS=OFF --configure-arg=-DENABLE_CJSON_TEST=ON
```

The host triple becomes `aarch64-unknown-nto-qnx8.0.0` and the CMake toolchain uses
`gcc_ntoaarch64le`. To run the results, build an aarch64le QEMU image once. You need three
packages from the QNX Software Center: the QEMU virt BSP (`com.qnx.qnx800.target.qemuvirt`),
the virtio block driver (`com.qnx.qnx800.target.driver.virtio.devb`) and
`qemu-system-aarch64`.

```sh
mkdir -p ~/qnx800/images/qemu-aarch64 && cd ~/qnx800/images/qemu-aarch64
mkqnximage --type=qemu --arch=aarch64le --ssh-ident=none --data-size=200 --build
# OpenSSH in SDP 8.0 needs its sshd-auth helper, which the image template doesn't install yet:
echo 'bin/sshd-auth=usr/libexec/sshd-auth' >> local/snippets/system_files.custom
echo '[type=link] /usr/libexec/sshd-auth=/system/bin/sshd-auth' >> local/snippets/ifs_files.custom
mkqnximage --build
```

`run` reads the architecture from the ELF header, so the command doesn't change:

```sh
qnx-port-doctor run --stdin in.json a64/jq-1.8.1/jq -- -c '.os'
```

On our machine jq's test suite gives the same 509/522 on Arm as on x86_64, and all 18 cJSON
test suites pass:

```sh
(cd cjson-a64/tests && tar czf ../../cjson-tests-a64.tgz cjson_add compare_tests minify_tests \
   misc_tests parse_* print_* readme_examples inputs)
qnx-port-doctor run --file cjson-tests-a64.tgz examples/cjson-tests.sh   # suites passed: 18 failed: 0
```

Build the tests statically (`BUILD_SHARED_LIBS=OFF`), because `run` copies single files. A shared build
fails on the target with `Could not load library libcjson.so.1`. The Arm VM is fully
emulated (no KVM on an x86 host), so the first boot is slower than on x86_64.

> **Troubleshooting:** if the VM boots (`Startup complete`) but ssh never answers and the log says
> `/usr/libexec/sshd-auth does not exist`, add the two snippet lines above and run `mkqnximage --build` again.
> If the boot log shows `devb-virtio: cannot execute` followed by
> `Unable to access /dev/hd0`, the virtio block driver package is missing. mkqnximage
> only warns about it (`Host file 'sbin/devb-virtio' missing`).

## 9. Put it in CI

```sh
qnx-port-doctor scan . -f sarif -o qnx.sarif --fail-on never
```

Upload `qnx.sarif` with GitHub's `upload-sarif` action, and the findings appear as code
scanning alerts on the lines they refer to. Or gate merges with
`qnx-port-doctor scan . --fail-on warning`.

## 10. What you learned

| QNX difference | Rule | Typical fix |
|---|---|---|
| `_XOPEN_SOURCE` must carry a version | QPD035 | `#define _XOPEN_SOURCE 700` (auto) |
| no `SA_RESTART` | QPD039 | guarded fallback to 0, handle `EINTR` (auto) |
| no compile-time `IOV_MAX` | QPD044 | `UIO_MAXIOV` fallback (auto) |
| `strptime` lacks `%F %T %D %R` | QPD037 | spell the format out (auto for literals) |
| sockets and regex outside libc | QPD045/046 | link `-lsocket`, `-lregex` (`build` adds them) |
| no epoll/inotify/eventfd/timerfd | QPD001–006 | `poll()`, pipes, `timer_create()`, QNX pulses |
| no Linux `/proc` layout | QPD040/041 | `devctl(DCMD_PROC_*)`, `sysconf()` |

Next ideas: try `--arch aarch64le`, add a project-specific rule in your own YAML file,
or point the scanner at a CMake project and let `build` generate the QNX toolchain file.
