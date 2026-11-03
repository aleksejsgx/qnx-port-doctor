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
_FEATURE = re.compile(r"\b(\w*?(?:HAVE|USE|ENABLE|HAS)_[A-Za-z0-9_]+)\b")
_DEFINED = re.compile(r"\bdefined\s*\(?\s*([A-Za-z_]\w*)")
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
    if directive == "ifdef":
        m = re.match(r"\s*([A-Za-z_]\w*)", pos)
        if m:
            return m.group(1)
    m = _DEFINED.search(pos)
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
# Per-platform sources for other systems (never compiled for QNX).
_OTHER_OS = r"linux|android|darwin|macos|osx|apple|ios|freebsd|netbsd|openbsd|dragonfly|bsd|sunos|solaris|illumos|aix|os390|zos|ibmi|os400|haiku|cygwin|msys|mingw|win32|win|windows|hpux|hurd"
_OS_NAME = re.compile(r"(^|[-_./])(" + _OTHER_OS + r")([-_.]|$)", re.I)
_CMAKE_OS = re.compile(r"(" + _OTHER_OS + r"|WIN32|APPLE|UNIX AND NOT)", re.I)


def _automake_conditionals(text, relbase):
    out = {}
    cond = []
    platform_var = None
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
        m = re.match(r"^(\w*(?:PLATFORM|DEPENDENT|LINUX)\w*)\s*\+?=", s, re.I)
        if m:
            platform_var = m.group(1)
        if platform_var:
            for tok in re.findall(r"[\w./@-]+\.(?:c|cc|cpp|cxx)\b", s):
                out[os.path.normpath(os.path.join(relbase, tok))] = f"Automake {platform_var}"
            if not s.endswith("\\"):
                platform_var = None
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
            c = m.group(2)
            linux = (bool(_CMAKE_OS.search(c)) and "NOT" not in c and not re.search(r"QNX", c, re.I)
                     and "UNIX AND NOT" not in c.upper())
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
                out[os.path.normpath(os.path.join(relbase, tok))] = "CMake platform-specific branch"
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
    base = os.path.splitext(os.path.basename(rel))[0]
    m = _OS_NAME.search(base)
    if m:
        return f"{m.group(2)}-specific file name (per-platform source)"
    parts = rel.replace(os.sep, "/").split("/")[:-1]
    for d in parts:
        if re.fullmatch(_OTHER_OS, d, re.I):
            return f"{d}-specific directory"
    return None


def comment_lines(lines):
    """Line numbers that are entirely inside /* ... */ comments (best effort)."""
    res, inside = set(), False
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if inside:
            res.add(no)
            if "*/" in s:
                inside = False
            continue
        if s.startswith("//"):
            res.add(no)
        elif s.startswith("/*"):
            res.add(no)
            if "*/" not in s[2:]:
                inside = True
        elif "/*" in s and "*/" not in s.split("/*", 1)[1]:
            inside = True
    return res


def build_file_guards(lines, name):
    """Map line number -> reason for build-file lines inside a conditional block.

    Automake: `if COND ... else ... endif` (the else branch counts as conditional too,
    because it is only used when COND is false on the build host).
    CMake: `if(<platform test>) ... endif()` for non-QNX platforms.
    """
    res, stack = {}, []
    is_am = name == "Makefile.am" or name.endswith(".am")
    is_cmake = name == "CMakeLists.txt" or name.endswith(".cmake")
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if is_am:
            m = re.match(r"^if\s+(!?\w+)", s)
            if m:
                stack.append(f"Automake `if {m.group(1)}`")
                continue
            if re.match(r"^else\b", s) and stack:
                stack[-1] = stack[-1].replace("`if ", "`else of ")
                continue
            if re.match(r"^endif\b", s) and stack:
                stack.pop()
                continue
        elif is_cmake:
            m = re.match(r"^(if|elseif)\s*\((.*)\)", s, re.I)
            if m:
                c = m.group(2)
                plat = (bool(_CMAKE_OS.search(c)) and "NOT" not in c and not re.search("QNX", c, re.I))
                label = f"CMake `if({c.strip()})`" if plat else None
                if m.group(1).lower() == "if":
                    stack.append(label)
                elif stack:
                    stack[-1] = label
                continue
            if re.match(r"^else\s*\(", s, re.I) and stack:
                stack[-1] = None
                continue
            if re.match(r"^endif\s*\(", s, re.I) and stack:
                stack.pop()
                continue
        for g in reversed(stack):
            if g:
                res[no] = g
                break
    return res
