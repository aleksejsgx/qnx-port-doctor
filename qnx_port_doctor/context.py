"""Project context: which code is already conditional on Linux or on configure checks.

Two sources of evidence reduce false positives:
  * preprocessor guards inside a file (#ifdef __linux__, #if HAVE_EPOLL, ...);
  * build-system conditionals that only compile a file on Linux or when a feature
    probe succeeds (Automake `if HAVE_X`, CMake `if(... Linux ...)`, Meson
    `host_machine.system() == 'linux'`), plus per-platform file naming
    (foo-linux.c, osdep-@PLATFORM@.c, linux/ directories).
"""
import os
import re

_IF = re.compile(r"^\s*#\s*(if|ifdef|ifndef)\b(.*)")
_ELIF = re.compile(r"^\s*#\s*elif\b(.*)")
_ELSE = re.compile(r"^\s*#\s*else\b")
_ENDIF = re.compile(r"^\s*#\s*endif\b")
_LINUX = re.compile(r"\b(__linux__|__linux|linux|__gnu_linux__|__GLIBC__|_GNU_SOURCE)\b")
_FEATURE = re.compile(r"\b((?:HAVE|USE|ENABLE|HAS)_[A-Z0-9_]+)\b")
_QNX = re.compile(r"__QNX__|__QNXNTO__")


def _classify(expr, directive):
    """Return a guard label if the *true* branch of this condition is Linux/feature specific."""
    if directive == "ifndef" or _QNX.search(expr):
        return None
    pos = re.sub(r"!\s*defined\s*\(?\s*\w+\s*\)?|!\s*\w+", " ", expr)  # drop negated terms
    m = _LINUX.search(pos)
    if m:
        return m.group(1)
    m = _FEATURE.search(pos)
    if m:
        return m.group(1)
    return None


def guards(lines):
    """Map line number -> guard label for lines inside a Linux/feature-specific branch."""
    stack, res = [], {}
    for no, line in enumerate(lines, 1):
        m = _IF.match(line)
        if m:
            stack.append(_classify(m.group(2), m.group(1)))
            continue
        m = _ELIF.match(line)
        if m and stack:
            stack[-1] = _classify(m.group(1), "if")
            continue
        if _ELSE.match(line) and stack:
            stack[-1] = None
            continue
        if _ENDIF.match(line) and stack:
            stack.pop()
            continue
        for g in reversed(stack):
            if g:
                res[no] = g
                break
    return res


_LINUX_NAME = re.compile(r"(^|[-_./])linux([-_.]|$)", re.I)


def _automake_conditionals(text, relbase):
    out = {}
    cond = []
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"^if\s+(!?\w+)", s)
        if m:
            cond.append(m.group(1))
            continue
        if s.startswith("else") and cond:
            cond[-1] = "!" + cond[-1].lstrip("!")
            continue
        if s.startswith("endif") and cond:
            cond.pop()
            continue
        active = [c for c in cond if not c.startswith("!")]
        if active:
            for tok in re.findall(r"[\w./@-]+\.(?:c|cc|cpp|cxx)\b", s):
                out[os.path.normpath(os.path.join(relbase, tok))] = f"Automake `if {active[-1]}`"
    return out


def _cmake_conditionals(text, relbase):
    out, cond = {}, []
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"^(if|elseif)\s*\((.*)\)", s, re.I)
        if m:
            linux = bool(re.search(r"linux", m.group(2), re.I)) and "NOT" not in m.group(2)
            if m.group(1).lower() == "if":
                cond.append(linux)
            elif cond:
                cond[-1] = linux
            continue
        if re.match(r"^else\s*\(", s, re.I) and cond:
            cond[-1] = False
            continue
        if re.match(r"^endif\s*\(", s, re.I) and cond:
            cond.pop()
            continue
        if any(cond):
            for tok in re.findall(r"[\w./${}-]+\.(?:c|cc|cpp|cxx)\b", s):
                tok = tok.replace("${CMAKE_CURRENT_SOURCE_DIR}/", "")
                out[os.path.normpath(os.path.join(relbase, tok))] = "CMake Linux-only branch"
    return out


def build_conditionals(root):
    """Return {relative source path: reason} for files compiled only conditionally."""
    out = {}
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in {".git", "build", "node_modules"}]
        rel = os.path.relpath(dp, root)
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                if fn == "Makefile.am":
                    out.update(_automake_conditionals(open(p, errors="replace").read(), rel))
                elif fn == "CMakeLists.txt" or fn.endswith(".cmake"):
                    out.update(_cmake_conditionals(open(p, errors="replace").read(), rel))
            except OSError:
                pass
    return out


def file_reason(rel, conditionals):
    rel = os.path.normpath(rel)
    if rel in conditionals:
        return conditionals[rel]
    if _LINUX_NAME.search(os.path.basename(rel)) or "/linux/" in "/" + rel.replace(os.sep, "/"):
        return "Linux-specific file name (per-platform source)"
    return None
