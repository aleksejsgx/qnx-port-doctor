# qnx-port-doctor

A command-line doctor for porting C/C++ projects to **QNX SDP 8.0**.

* **scan** a source tree for QNX portability blockers: Linux-only headers and APIs
  (epoll, inotify, prctl, eventfd, timerfd, `linux/*`), glibc-isms, Linux `/proc` and sysfs
  paths, QNX quirks (`SA_RESTART`, `IOV_MAX`, empty `_XOPEN_SOURCE`, `strptime("%F")`),
  and link flags (`-lrt`, `-ldl`, missing `-lsocket`/`-lregex`);
* understands project context: code behind `#ifdef __linux__` / `HAVE_*` guards, files only
  compiled under Automake/CMake conditionals, and per-platform sources are downgraded to `info`;
* **fix**: writes a reviewable unified diff for auto-fixable rules (`patch -p1` ready);
* **build**: cross-builds with `qcc` (single file, make, CMake toolchain, or `--autotools`);
* **run**: boots the QNX QEMU quickstart image, copies the binary in over ssh and runs it;
* reports as text, Markdown, JSON or **SARIF 2.1.0** (GitHub code scanning).

```sh
pip install -e .
qnx-port-doctor scan path/to/project                     # human-readable
qnx-port-doctor scan path -f md -o report.md             # Markdown
qnx-port-doctor scan path -f sarif -o qnx.sarif          # code scanning
qnx-port-doctor fix path -o qnx.patch                    # review, then: patch -p1 < qnx.patch
source ~/qnx800/qnxsdp-env.sh
qnx-port-doctor build path --autotools --prefix $SYSROOT # configure --host=x86_64-pc-nto-qnx8.0.0
qnx-port-doctor run ./prog -- --version                  # runs inside QNX on QEMU
qnx-port-doctor rules                                    # list rules ("fix" = auto-fixable)
```

Start with the tutorial: [examples/TUTORIAL.md](examples/TUTORIAL.md).
Real-world results: [examples/PORTING-LOG.md](examples/PORTING-LOG.md).

## Rules

Rules live in `qnx_port_doctor/data/rules.yaml`. Add your own with `--rules my.yaml`
(entries with an existing id override the bundled rule):

```yaml
rules:
- id: ACME001
  severity: error          # error | warning | info
  kind: api                # include | api | path | macro | link
  pattern: '\bmy_linux_only_call\s*\('
  title: my_linux_only_call() has no QNX implementation
  fix: Use acme_portable_call() instead.
  guardable: true          # false = also flag inside #ifdef blocks (QNX quirks)
```

Auto-fixable rules carry `autofix: <fixer>`; fixers live in `qnx_port_doctor/fixes.py`
and only produce edits that are valid on every platform (guarded fallbacks or
spelled-out formats).

## Exit codes

`scan` exits 1 when findings at or above `--fail-on` (default `error`) remain, so it can gate CI.

## Running on QNX (QEMU)

Defaults: image `~/qnx800/images/qemu/qemu`, ssh port 2222, user `qnxuser`
(password from `--password` or `QPD_PASSWORD`). `--keep` leaves the VM up for fast re-runs;
`--file` copies extra files; `--stdin` feeds a local file to the program.

License: MIT
