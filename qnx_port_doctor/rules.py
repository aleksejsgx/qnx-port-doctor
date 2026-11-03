"""Rule database loader. Rules live in data/rules.yaml; extra files can be merged in."""
import os
from dataclasses import dataclass

import yaml

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DEFAULT_RULES = os.path.join(DATA_DIR, "rules.yaml")
SEVERITIES = ("error", "warning", "info")
KINDS = ("include", "api", "path", "macro", "link")


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str  # error | warning | info
    kind: str  # include | api | link | path | macro
    pattern: str  # Python regex
    title: str
    fix: str
    guardable: bool = True  # False: affects code that *is* compiled on QNX despite guards
    autofix: str = ""  # name of a fixer in fixes.py, empty if manual


def load_rules(paths=None):
    """Load rules from the bundled YAML plus optional extra files (later ids override earlier)."""
    by_id = {}
    for path in [DEFAULT_RULES, *(paths or [])]:
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        for i, d in enumerate(doc.get("rules", [])):
            missing = {"id", "severity", "kind", "pattern", "title", "fix"} - set(d)
            if missing:
                raise ValueError(f"{path}: rule #{i} missing {sorted(missing)}")
            if d["severity"] not in SEVERITIES or d["kind"] not in KINDS:
                raise ValueError(f"{path}: rule {d['id']} has invalid severity/kind")
            by_id[d["id"]] = Rule(**{k: d[k] for k in Rule.__dataclass_fields__ if k in d})
    return list(by_id.values())


RULES = load_rules()

SOURCE_EXT = {".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"}
BUILD_FILES = {"Makefile", "makefile", "GNUmakefile", "CMakeLists.txt", "configure.ac", "configure.in",
               "meson.build", "Makefile.am", "Makefile.in"}
