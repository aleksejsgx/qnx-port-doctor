"""Walk a source tree and match rules."""
import os
import re
from dataclasses import dataclass, asdict

from .rules import RULES, SOURCE_EXT, BUILD_FILES
from .context import guards, build_conditionals, file_reason

SKIP_DIRS = {".git", "build", "node_modules", ".svn", "__pycache__"}


@dataclass
class Finding:
    rule: str
    severity: str
    file: str
    line: int
    text: str
    title: str
    fix: str
    note: str = ""

    def to_dict(self):
        return asdict(self)


_compiled = [(r, re.compile(r.pattern)) for r in RULES]


def _is_build_file(name):
    return name in BUILD_FILES or name.endswith((".mk", ".cmake"))


def scan_file(path, rel, conditionals=None):
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1]
    if ext in SOURCE_EXT:
        kinds = {"include", "api", "path", "macro"}
    elif _is_build_file(name):
        kinds = {"link"}
    else:
        return []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return []
    out = []
    guarded = guards(lines) if ext in SOURCE_EXT else {}
    freason = file_reason(rel, conditionals or {}) if ext in SOURCE_EXT else None
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if ext in SOURCE_EXT and s.startswith(("//", "*", "/*")):
            continue
        for rule, rx in _compiled:
            if rule.kind not in kinds:
                continue
            # socket hint only meaningful when linking is configured: skip noisy rule in source
            if rx.search(line):
                sev, note = rule.severity, ""
                if rule.kind != "macro":
                    if no in guarded:
                        sev, note = "info", f"guarded by {guarded[no]}; verify the QNX build leaves it undefined"
                    elif freason:
                        sev, note = "info", f"conditionally compiled ({freason})"
                out.append(Finding(rule.id, sev, rel, no, s[:160], rule.title, rule.fix, note))
    return out


def scan(root):
    findings = []
    if os.path.isfile(root):
        return scan_file(root, os.path.basename(root))
    conditionals = build_conditionals(root)
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in SKIP_DIRS)
        for fn in sorted(fns):
            p = os.path.join(dp, fn)
            findings.extend(scan_file(p, os.path.relpath(p, root), conditionals))
    return findings


