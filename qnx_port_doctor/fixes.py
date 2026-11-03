"""Automatic fixes for selected rules, emitted as reviewable unified diffs.

Fixers are deliberately conservative: each one either edits the matched line in
a way that is valid on every platform, or inserts a guarded fallback block
(`#ifndef X ... #endif`) that is a no-op where X already exists.
"""
import difflib
import os
import re

from .scanner import scan

_INCLUDE = re.compile(r"^\s*#\s*include\b")
_IF = re.compile(r"^\s*#\s*if")
_ENDIF = re.compile(r"^\s*#\s*endif\b")


def _insert_point(lines):
    """Index after the last top-level #include (depth 0, ignoring a header guard)."""
    depth, last, guard_depth = 0, None, 0
    first_directive = next((l for l in lines if l.strip().startswith("#")), "")
    if re.match(r"^\s*#\s*ifndef\s+\w+_H", first_directive):
        guard_depth = 1
    for i, line in enumerate(lines):
        if _IF.match(line):
            depth += 1
        elif _ENDIF.match(line):
            depth -= 1
        elif _INCLUDE.match(line) and depth <= guard_depth:
            last = i
    return 0 if last is None else last + 1


def fix_xopen_value(lines, idx, state):
    lines[idx] = re.sub(r"(#\s*define\s+_XOPEN_SOURCE)\b(\s*\d+)?", r"\1 700", lines[idx], count=1)


_STRPTIME = {"%F": "%Y-%m-%d", "%T": "%H:%M:%S", "%D": "%m/%d/%y", "%R": "%H:%M"}


def fix_strptime_expand(lines, idx, state):
    line = lines[idx]
    m = re.search(r"\bstrptime\s*\(", line)
    if not m:
        return
    head, tail = line[:m.end()], line[m.end():]
    for k, v in _STRPTIME.items():
        tail = tail.replace(k, v)
    lines[idx] = head + tail


class _State(set):
    def __init__(self):
        super().__init__()
        self.pending = []


def fix_guard_sa_restart(lines, idx, state):
    if "SA_RESTART" not in state:
        state.add("SA_RESTART")
        state.pending.append(["/* QNX 8 does not provide SA_RESTART; interrupted calls return EINTR. */",
                              "#ifndef SA_RESTART", "#define SA_RESTART 0", "#endif"])


def fix_iov_max_fallback(lines, idx, state):
    if "IOV_MAX" not in state:
        state.add("IOV_MAX")
        state.pending.append(["/* QNX <limits.h> does not define IOV_MAX; use the kernel limit. */",
                              "#ifndef IOV_MAX", "#include <sys/uio.h>", "#define IOV_MAX UIO_MAXIOV", "#endif"])


FIXERS = {
    "xopen_value": fix_xopen_value,
    "strptime_expand": fix_strptime_expand,
    "guard_sa_restart": fix_guard_sa_restart,
    "iov_max_fallback": fix_iov_max_fallback,
}


def plan(root, rules=None, include_info=False):
    """Return {relative path: (original_text, fixed_text, [rule ids])}."""
    findings = [f for f in scan(root, rules) if f.autofix and (include_info or f.severity != "info")]
    by_file = {}
    for f in findings:
        by_file.setdefault(f.file, []).append(f)
    base = root if os.path.isdir(root) else os.path.dirname(root)
    result = {}
    for rel, fs in sorted(by_file.items()):
        path = os.path.join(base, rel)
        with open(path, encoding="utf-8", errors="surrogateescape", newline="") as fh:
            text = fh.read()
        eol = "\r\n" if "\r\n" in text else "\n"
        lines = text.split(eol)
        state = _State()
        for f in sorted(fs, key=lambda x: x.line):
            FIXERS[f.autofix](lines, f.line - 1, state)
        if state.pending:
            at = _insert_point(lines)
            block = [""]
            for b in state.pending:
                block += b
            lines[at:at] = block
        new = eol.join(lines)
        if new != text:
            result[rel] = (text, new, sorted({f.rule for f in fs}))
    return result


def unified_diff(changes):
    out = []
    for rel, (old, new, ids) in changes.items():
        rel = rel.replace(os.sep, "/")
        out.append(f"# qnx-port-doctor: {rel}: {', '.join(ids)}\n")
        out.extend(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                        fromfile=f"a/{rel}", tofile=f"b/{rel}"))
    return "".join(out)


def apply(root, changes):
    base = root if os.path.isdir(root) else os.path.dirname(root)
    for rel, (_, new, _) in changes.items():
        with open(os.path.join(base, rel), "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
            fh.write(new)
