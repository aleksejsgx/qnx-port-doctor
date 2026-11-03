# Porting log: real projects on QNX SDP 8.0 (x86_64, QEMU)

| Project | Scanner (before fixes) | Real build blockers | Result on QNX |
|---|---|---|---|
| jq 1.8.1 | 1 error: QPD035 empty `_XOPEN_SOURCE` (src/builtin.c) | same | builds; `--run-tests` 509/522 (failures: module fixtures not copied; `strptime("%FT%T")` -> QPD037) |
| libevent 2.1.12 | SA_RESTART (signal.c) | `SA_RESTART` undeclared | builds static after `#ifdef SA_RESTART` |
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
