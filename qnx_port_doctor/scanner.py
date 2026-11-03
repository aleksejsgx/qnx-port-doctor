"""Walk a source tree and match rules."""
import os
import re
from dataclasses import dataclass, asdict

from .rules import RULES, SOURCE_EXT, BUILD_FILES

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

    def to_dict(self):
        return asdict(self)


_compiled = [(r, re.compile(r.pattern)) for r in RULES]


def _is_build_file(name):
    return name in BUILD_FILES or name.endswith((".mk", ".cmake"))


def scan_file(path, rel):
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
    guarded = guarded_lines(lines) if ext in SOURCE_EXT else set()
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if ext in SOURCE_EXT and s.startswith(("//", "*", "/*")):
            continue
        for rule, rx in _compiled:
            if rule.kind not in kinds:
                continue
            # socket hint only meaningful when linking is configured: skip noisy rule in source
            if rx.search(line):
                sev = rule.severity
                if no in guarded and rule.kind != "macro":
                    sev = "info"  # already behind a Linux-only guard
                out.append(Finding(rule.id, sev, rel, no, s[:160], rule.title, rule.fix))
    return out


def scan(root):
    findings = []
    if os.path.isfile(root):
        return scan_file(root, os.path.basename(root))
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in SKIP_DIRS)
        for fn in sorted(fns):
            p = os.path.join(dp, fn)
            findings.extend(scan_file(p, os.path.relpath(p, root)))
    return findings


_IF = re.compile(r"^\s*#\s*(if|ifdef|ifndef)\b(.*)")
_ELSE = re.compile(r"^\s*#\s*(else|elif)\b")
_ENDIF = re.compile(r"^\s*#\s*endif\b")
_LINUX = re.compile(r"__linux__|__linux\b|\bHAVE_(EPOLL|INOTIFY|PRCTL|EVENTFD|SYS_PRCTL_H|LINUX)")


def guarded_lines(lines):
    """Line numbers inside a positive Linux-only #if/#ifdef branch (best effort)."""
    stack, res = [], set()
    for no, line in enumerate(lines, 1):
        m = _IF.match(line)
        if m:
            linux = bool(_LINUX.search(m.group(2))) and m.group(1) != "ifndef" and "!" not in m.group(2)
            stack.append(linux)
            continue
        if _ELSE.match(line) and stack:
            stack[-1] = False
            continue
        if _ENDIF.match(line) and stack:
            stack.pop()
            continue
        if any(stack):
            res.add(no)
    return res
