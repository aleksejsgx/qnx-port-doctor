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


def test_build_file_conditionals(tmp_path):
    from qnx_port_doctor.scanner import scan
    (tmp_path / "Makefile.am").write_text("bin_LDADD = -lrt\nif ENABLE_X\nfoo_LIBADD = -ldl\nendif\n")
    (tmp_path / "CMakeLists.txt").write_text(
        'if(CMAKE_SYSTEM_NAME STREQUAL "Linux")\n  target_link_libraries(x -ldl)\nendif()\n'
        'target_link_libraries(y -lrt)\n')
    sev = {(f.file, f.line): f.severity for f in scan(str(tmp_path)) if f.rule == "QPD060"}
    assert sev[("Makefile.am", 1)] == "warning" and sev[("Makefile.am", 3)] == "info"
    assert sev[("CMakeLists.txt", 2)] == "info" and sev[("CMakeLists.txt", 4)] == "warning"


def test_qnx7_to_8_rules(tmp_path):
    from qnx_port_doctor.scanner import scan
    (tmp_path / "qnx.c").write_text("x = _SYSPAGE_ENTRY(_syspage_ptr, new_cpuinfo);\nu = qtime->nsec;\n")
    ids = {f.rule: f.severity for f in scan(str(tmp_path))}
    assert ids == {"QPD090": "error", "QPD091": "error"}
    assert "_SYSPAGE_ENTRY(_syspage_ptr, cpuinfo)" in fixes.unified_diff(fixes.plan(str(tmp_path)))


def test_other_platform_files(tmp_path):
    from qnx_port_doctor.scanner import scan
    (tmp_path / "os390-syscalls.h").write_text("int epoll_wait(int);\n")
    (tmp_path / "w.c").write_text("#if defined(_WIN32)\n#include <malloc.h>\n#endif\n#include <stdio.h> /* epoll_wait( */\n")
    assert all(f.severity == "info" for f in scan(str(tmp_path)))


def test_feature_conditional_file_keeps_quirks(tmp_path):
    from qnx_port_doctor.scanner import scan
    (tmp_path / "Makefile.am").write_text("if SIGNAL_SUPPORT\nSRC += signal.c\nendif\n")
    (tmp_path / "signal.c").write_text("void f(){ sa.sa_flags |= SA_RESTART; }\n#include <sys/epoll.h>\n")
    sev = {f.rule: f.severity for f in scan(str(tmp_path))}
    assert sev["QPD039"] == "warning"   # compiled on QNX too: still a blocker
    assert sev["QPD001"] == "info"      # Linux API in a feature-conditional file


def test_run_arch_detection_and_qemu_cmd(tmp_path):
    from qnx_port_doctor import run as qrun
    a64 = tmp_path / "a64"
    a64.write_bytes(b"\x7fELF\x02\x01\x01" + b"\0" * 11 + (183).to_bytes(2, "little"))
    x86 = tmp_path / "x86"
    x86.write_bytes(b"\x7fELF\x02\x01\x01" + b"\0" * 11 + (62).to_bytes(2, "little"))
    assert qrun.detect_arch(str(a64)) == "aarch64le"
    assert qrun.detect_arch(str(x86)) == "x86_64"
    assert qrun.detect_arch(str(tmp_path)) is None
    cmd = qrun.qemu_cmd("/img", 2223, arch="aarch64le")
    assert cmd[0] == "qemu-system-aarch64" and "virtio-blk-device,drive=drv0" in cmd
    assert "hostfwd=tcp:127.0.0.1:2223-:22" in " ".join(cmd)


def test_socket_probe_rule_not_noisy(tmp_path):
    from qnx_port_doctor.scanner import scan
    (tmp_path / "Makefile.am").write_text("SRCS = cmd-bind-key.c socket.c\n")
    (tmp_path / "configure.ac").write_text("AC_SEARCH_LIBS([socket], [socket])\n")
    hits = [(f.file, f.rule) for f in scan(str(tmp_path)) if f.rule == "QPD061"]
    assert hits == [("configure.ac", "QPD061")]
