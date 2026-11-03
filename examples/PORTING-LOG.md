# Porting log: real projects on QNX SDP 8.0 (x86_64, QEMU)

| Project | Scanner (before fixes) | Real build blockers | Result on QNX |
|---|---|---|---|
| jq 1.8.1 | 1 error: QPD035 empty `_XOPEN_SOURCE` (src/builtin.c) | same | builds; `--run-tests` 509/522 (failures: module fixtures not copied; `strptime("%FT%T")` -> QPD037) |
| libevent 2.1.12 | SA_RESTART (signal.c) | `SA_RESTART` undeclared | builds static after `#ifdef SA_RESTART` |
| cJSON 1.7.18 (CMake) | clean | none (CMake 4 needs `CMAKE_POLICY_VERSION_MINIMUM`, set by `build`) | 18/18 test suites pass |
| libuv 1.49.2 (CMake, has a QNX backend) | 2 errors: QPD090 `new_cpuinfo`, QPD091 `qtime->nsec` (QNX 7 APIs) | same | builds after `libuv-1.49.2-qnx8.patch`; 24/26 selected tests pass (fs_event_watch_file, process_title fail) |
| tmux 3.5a | 8 warnings: SA_RESTART x4, IOV_MAX x4 | same, plus link libs -lsocket, -lregex | builds; new-session/split-window/capture-pane work |

## Recipes

```sh
source ~/qnx800/qnxsdp-env.sh
HOST=x86_64-pc-nto-qnx8.0.0; CC="qcc -Vgcc_ntox86_64"
COMPAT=$(qnx-port-doctor compat-header)

# jq (release tarball)
./configure --host=$HOST CC="$CC" --without-oniguruma --disable-docs --disable-shared --enable-static
make src/builtin.inc && make -j8

# libevent
./configure --host=$HOST CC="$CC" --disable-shared --disable-openssl --disable-samples \
  --disable-libevent-regress --prefix=$SYSROOT && make -j8 install

# tmux
PKG_CONFIG_LIBDIR=$SYSROOT/lib/pkgconfig ./configure --host=$HOST CC="$CC" \
  CPPFLAGS=-I$SYSROOT/include LDFLAGS=-L$SYSROOT/lib LIBS=-lsocket \
  LIBNCURSES_CFLAGS=" " LIBNCURSES_LIBS=-lncurses
make -j8 CPPFLAGS="-I$SYSROOT/include -include $COMPAT" LIBS="-lsocket -lregex -levent_core -lncurses -lm"

qnx-port-doctor run --file ./tmux tmux-smoke.sh
```

# cJSON (CMake): toolchain file generated automatically
qnx-port-doctor build cJSON-1.7.18 --out cjson-qnx --configure-arg=-DENABLE_CJSON_TEST=ON
(cd cjson-qnx/tests && tar czf ../../cjson-tests.tgz cjson_add compare_tests minify_tests misc_tests parse_* print_* readme_examples inputs)
qnx-port-doctor run --file cjson-tests.tgz examples/cjson-tests.sh

# libuv (CMake): QNX 7 -> 8 syspage changes
(cd libuv-v1.49.2 && patch -p1 < ../qnx-port-doctor/examples/libuv-1.49.2-qnx8.patch)   # or: qnx-port-doctor fix (QPD090), QPD091 is manual
qnx-port-doctor build libuv-v1.49.2 --out libuv-qnx --configure-arg=-DLIBUV_BUILD_TESTS=ON
qnx-port-doctor run --file libuv-qnx/uv_run_tests_a examples/libuv-tests.sh
```
