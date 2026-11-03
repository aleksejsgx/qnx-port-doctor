"""Command-line entry point."""
import argparse
import os
import sys

from . import __version__
from .scanner import scan
from .report import RENDERERS
from .rules import RULES, load_rules
from . import fixes
from . import build as qbuild
from . import run as qrun


def main(argv=None):
    p = argparse.ArgumentParser(prog="qnx-port-doctor", description="Find QNX portability blockers in C/C++ code.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="scan a source tree")
    s.add_argument("path")
    s.add_argument("-f", "--format", choices=sorted(RENDERERS), default="text")
    s.add_argument("-o", "--output")
    s.add_argument("--min-severity", choices=["error", "warning", "info"], default="info")
    s.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")
    s.add_argument("--rules", action="append", default=[], help="extra rules YAML (overrides by id)")
    rl = sub.add_parser("rules", help="list rules")
    rl.add_argument("--rules", action="append", default=[])
    fx = sub.add_parser("fix", help="write a unified-diff patch for auto-fixable findings")
    fx.add_argument("path")
    fx.add_argument("-o", "--output", help="patch file (default: stdout)")
    fx.add_argument("--apply", action="store_true", help="also modify the files in place")
    fx.add_argument("--include-guarded", action="store_true", help="also fix findings downgraded to info")
    fx.add_argument("--rules", action="append", default=[])
    sub.add_parser("compat-header", help="print path of qnx_compat.h (use with -include)")
    b = sub.add_parser("build", help="cross-build with QNX SDP")
    b.add_argument("path")
    b.add_argument("--arch", choices=sorted(qbuild.ARCH), default="x86_64")
    b.add_argument("--out", default="build-qnx")
    b.add_argument("--dry-run", action="store_true")
    b.add_argument("--autotools", action="store_true", help="configure --host=<qnx triple> && make")
    b.add_argument("--prefix", help="install prefix / sysroot with dependencies (adds -I/-L/pkg-config)")
    b.add_argument("--configure-arg", action="append", default=[], dest="configure_args",
                   help="extra ./configure or cmake argument (repeatable)")
    b.add_argument("--lib", action="append", default=[], dest="libs", help="extra -l flag, e.g. -lncurses")
    b.add_argument("--no-compat", action="store_true", help="do not force-include qnx_compat.h")
    b.add_argument("--env", action="append", default=[], metavar="K=V", help="extra environment for configure/make")
    b.add_argument("-j", "--jobs", type=int, default=8)
    t = sub.add_parser("toolchain", help="write a CMake toolchain file")
    t.add_argument("--arch", choices=sorted(qbuild.ARCH), default="x86_64")
    t.add_argument("-o", "--output", default="qnx.cmake")
    r = sub.add_parser("run", help="boot QNX in QEMU, copy a binary in and run it")
    r.add_argument("binary")
    r.add_argument("args", nargs="*")
    r.add_argument("--image", default=qrun.DEFAULT_IMAGE)
    r.add_argument("--port", type=int, default=2222)
    r.add_argument("--user", default="qnxuser")
    r.add_argument("--password", default=os.environ.get("QPD_PASSWORD", "qnxuser"))
    r.add_argument("--kvm", action="store_true", help="use KVM acceleration")
    r.add_argument("--keep", action="store_true", help="leave the VM running for later runs")
    r.add_argument("--file", action="append", default=[], help="extra file to copy next to the binary")
    r.add_argument("--stdin", help="local file fed to the program's stdin")
    r.add_argument("--boot-timeout", type=int, default=300)
    a = p.parse_args(argv)

    if a.cmd == "run":
        code, out, err = qrun.run(a.binary, a.args, a.image, a.port, a.user, a.password,
                                  a.boot_timeout, a.keep, a.kvm, a.file, a.stdin,
                                  log=lambda m: print(m, file=sys.stderr))
        sys.stdout.write(out)
        sys.stderr.write(err)
        print(f"[exit {code}]", file=sys.stderr)
        return code

    if a.cmd == "rules":
        for r in load_rules(a.rules):
            print(f"{r.id}  {r.severity:7} {r.kind:7} {'fix ' if r.autofix else '    '}{r.title}")
        return 0
    if a.cmd == "fix":
        changes = fixes.plan(a.path, load_rules(a.rules), a.include_guarded)
        patch = fixes.unified_diff(changes)
        if a.output:
            with open(a.output, "w") as fh:
                fh.write(patch)
        else:
            sys.stdout.write(patch)
        if a.apply:
            fixes.apply(a.path, changes)
        print(f"{len(changes)} file(s) {'patched' if a.apply else 'with proposed fixes'}", file=sys.stderr)
        return 0
    if a.cmd == "compat-header":
        print(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "qnx_compat.h"))
        return 0
    if a.cmd == "build":
        return qbuild.build(a.path, a.arch, a.out, a.dry_run, a.autotools, a.prefix,
                            a.configure_args, a.libs, not a.no_compat, a.jobs,
                            dict(e.split("=", 1) for e in a.env))
    if a.cmd == "toolchain":
        print(qbuild.write_toolchain(a.output, a.arch))
        return 0
    lvl = {"error": 0, "warning": 1, "info": 2}
    rules = load_rules(a.rules)
    fs = [f for f in scan(a.path, rules) if lvl[f.severity] <= lvl[a.min_severity]]
    out = RENDERERS[a.format](fs, a.path, rules) if a.format == "sarif" else RENDERERS[a.format](fs, a.path)
    if a.output:
        open(a.output, "w").write(out)
    else:
        sys.stdout.write(out)
    if a.fail_on != "never" and any(lvl[f.severity] <= lvl[a.fail_on] for f in fs):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
