import json
import os
import subprocess

from qnx_port_doctor import fixes
from qnx_port_doctor.cli import main
from qnx_port_doctor.rules import load_rules, RULES
from qnx_port_doctor.build import autotools_plan


def test_yaml_rules_loaded_and_override(tmp_path):
    assert len(RULES) >= 40 and all(r.id.startswith("QPD") for r in RULES)
    extra = tmp_path / "extra.yaml"
    extra.write_text("rules:\n- id: QPD001\n  severity: info\n  kind: include\n"
                     "  pattern: '#include <sys/epoll\\.h>'\n  title: t\n  fix: f\n"
                     "- id: ACME1\n  severity: error\n  kind: api\n  pattern: '\\bfoo\\('\n  title: no foo\n  fix: bar\n")
    rules = {r.id: r for r in load_rules([str(extra)])}
    assert rules["QPD001"].severity == "info" and "ACME1" in rules


def test_fix_patch_applies(tmp_path):
    src = tmp_path / "p"
    src.mkdir()
    (src / "a.c").write_text("#define _XOPEN_SOURCE\n#include <signal.h>\n#include <time.h>\n\n"
                             "void f(void){ struct sigaction sa; sa.sa_flags = SA_RESTART;\n"
                             "  strptime(s, \"%FT%T\", &t); }\n")
    (src / "b.c").write_text("#include <limits.h>\nstruct iovec v[IOV_MAX];\n")
    patch = fixes.unified_diff(fixes.plan(str(src)))
    assert "+#define _XOPEN_SOURCE 700" in patch
    assert "+#ifndef SA_RESTART" in patch and "+#define IOV_MAX UIO_MAXIOV" in patch
    assert '%Y-%m-%dT%H:%M:%S' in patch
    (tmp_path / "x.patch").write_text(patch)
    r = subprocess.run(["patch", "-p1", "-i", str(tmp_path / "x.patch")], cwd=src, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    b = (src / "b.c").read_text().splitlines()
    assert b.index("#ifndef IOV_MAX") > b.index("#include <limits.h>")
    assert fixes.plan(str(src)) == {}  # idempotent: nothing left to fix


def test_fix_cli_apply(tmp_path):
    (tmp_path / "a.c").write_text("#define _XOPEN_SOURCE\n")
    assert main(["fix", str(tmp_path), "--apply", "-o", str(tmp_path / "out.patch")]) == 0
    assert (tmp_path / "a.c").read_text() == "#define _XOPEN_SOURCE 700\n"


def test_sarif(tmp_path):
    (tmp_path / "a.c").write_text("#include <sys/epoll.h>\n")
    out = tmp_path / "r.sarif"
    main(["scan", str(tmp_path), "-f", "sarif", "-o", str(out), "--fail-on", "never"])
    d = json.loads(out.read_text())
    assert d["version"] == "2.1.0"
    res = d["runs"][0]["results"][0]
    assert res["ruleId"] == "QPD001" and res["level"] == "error"
    assert res["locations"][0]["physicalLocation"]["region"]["startLine"] == 1
    assert d["runs"][0]["tool"]["driver"]["rules"][res["ruleIndex"]]["id"] == "QPD001"


def test_autotools_plan(tmp_path):
    (tmp_path / "configure").write_text("")
    env, cmds = autotools_plan(str(tmp_path), "aarch64le", prefix="/sr", extra_libs=["-lncurses"])
    assert cmds[0][:2] == ["./configure", "--host=aarch64-unknown-nto-qnx8.0.0"]
    assert "-include" in env["CPPFLAGS"] and "-lsocket" in env["LIBS"] and "-lncurses" in env["LIBS"]
    assert env["PKG_CONFIG_LIBDIR"] == "/sr/lib/pkgconfig"
    env, cmds = autotools_plan(str(tmp_path / "nope"), compat=False)
    assert cmds[0] == ["autoreconf", "-fi"] and "-include" not in env["CPPFLAGS"]
