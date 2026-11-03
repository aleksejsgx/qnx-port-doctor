"""Command-line entry point."""
import argparse
import sys

from . import __version__
from .scanner import scan
from .report import RENDERERS
from .rules import RULES
from . import build as qbuild


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
    sub.add_parser("rules", help="list rules")
    b = sub.add_parser("build", help="cross-build with QNX SDP")
    b.add_argument("path")
    b.add_argument("--arch", choices=sorted(qbuild.ARCH), default="x86_64")
    b.add_argument("--out", default="build-qnx")
    b.add_argument("--dry-run", action="store_true")
    t = sub.add_parser("toolchain", help="write a CMake toolchain file")
    t.add_argument("--arch", choices=sorted(qbuild.ARCH), default="x86_64")
    t.add_argument("-o", "--output", default="qnx.cmake")
    a = p.parse_args(argv)

    if a.cmd == "rules":
        for r in RULES:
            print(f"{r.id}  {r.severity:7} {r.kind:7} {r.title}")
        return 0
    if a.cmd == "build":
        return qbuild.build(a.path, a.arch, a.out, a.dry_run)
    if a.cmd == "toolchain":
        print(qbuild.write_toolchain(a.output, a.arch))
        return 0
    lvl = {"error": 0, "warning": 1, "info": 2}
    fs = [f for f in scan(a.path) if lvl[f.severity] <= lvl[a.min_severity]]
    out = RENDERERS[a.format](fs, a.path)
    if a.output:
        open(a.output, "w").write(out)
    else:
        sys.stdout.write(out)
    if a.fail_on != "never" and any(lvl[f.severity] <= lvl[a.fail_on] for f in fs):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
