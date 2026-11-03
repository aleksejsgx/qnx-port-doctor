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
