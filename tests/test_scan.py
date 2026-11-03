import json, os
from qnx_port_doctor.scanner import scan
from qnx_port_doctor.cli import main

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def test_detects_rules():
    ids = {f.rule for f in scan(FIX)}
    assert {"QPD001", "QPD003", "QPD020", "QPD031", "QPD040", "QPD060"} <= ids


def test_json_and_exit(tmp_path, capsys):
    out = tmp_path / "r.json"
    assert main(["scan", FIX, "-f", "json", "-o", str(out)]) == 1
    d = json.loads(out.read_text())
    assert d["summary"]["error"] >= 2


def test_clean(tmp_path):
    (tmp_path / "a.c").write_text("#include <stdio.h>\nint main(){return 0;}\n")
    assert main(["scan", str(tmp_path)]) == 0


def test_build_dry_run(capsys):
    assert main(["build", os.path.join(FIX, "linuxy.c"), "--dry-run"]) == 0
    assert "qcc -Vgcc_ntox86_64" in capsys.readouterr().out


def test_guarded_downgraded(tmp_path):
    (tmp_path / "g.c").write_text("#ifdef __linux__\n#include <sys/epoll.h>\n#else\n#include <sys/epoll.h>\n#endif\n")
    sev = {f.line: f.severity for f in scan(str(tmp_path)) if f.rule == "QPD001"}
    assert sev == {2: "info", 4: "error"}


def test_have_guard_and_ifndef(tmp_path):
    (tmp_path / "g.c").write_text(
        "#if defined(HAVE_PRCTL) && defined(HAVE_PR_SET_NAME)\n#include <sys/prctl.h>\n#endif\n"
        "#ifndef HAVE_EPOLL\n#include <sys/epoll.h>\n#endif\n"
        "#if !defined(__linux__)\n#include <sys/eventfd.h>\n#endif\n")
    sev = {f.rule: (f.severity, f.note) for f in scan(str(tmp_path))}
    assert sev["QPD003"][0] == "info" and "HAVE_PRCTL" in sev["QPD003"][1]
    assert sev["QPD001"][0] == "error"
    assert sev["QPD004"][0] == "error"


def test_build_conditional_and_linux_name(tmp_path):
    (tmp_path / "Makefile.am").write_text("bin_SOURCES = a.c\nif HAVE_KEYCTL\nbin_SOURCES += compat/keyring.c\nendif\n")
    (tmp_path / "compat").mkdir()
    (tmp_path / "compat" / "keyring.c").write_text("#include <linux/keyctl.h>\n")
    (tmp_path / "osdep-linux.c").write_text("#include <sys/inotify.h>\n")
    (tmp_path / "CMakeLists.txt").write_text('if(CMAKE_SYSTEM_NAME STREQUAL "Linux")\n  target_sources(x PRIVATE ev.c)\nendif()\n')
    (tmp_path / "ev.c").write_text("#include <sys/epoll.h>\n")
    fs = {f.file: f for f in scan(str(tmp_path))}
    assert fs[os.path.join("compat", "keyring.c")].severity == "info"
    assert "HAVE_KEYCTL" in fs[os.path.join("compat", "keyring.c")].note
    assert fs["osdep-linux.c"].severity == "info"
    assert fs["ev.c"].severity == "info"


def test_xopen_and_strptime(tmp_path):
    (tmp_path / "x.c").write_text('#define _XOPEN_SOURCE\nvoid f(){strptime(s, "%FT%T", &t);}\n')
    ids = {f.rule: f.severity for f in scan(str(tmp_path))}
    assert ids["QPD035"] == "error" and ids["QPD037"] == "warning"
