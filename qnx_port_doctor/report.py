"""Report renderers: text, markdown, json."""
import json
import os
from collections import Counter

ORDER = {"error": 0, "warning": 1, "info": 2}


def _sorted(fs):
    return sorted(fs, key=lambda f: (ORDER[f.severity], f.file, f.line))


def summary(fs):
    c = Counter(f.severity for f in fs)
    return {k: c.get(k, 0) for k in ("error", "warning", "info")}


def render_text(fs, root):
    s = summary(fs)
    out = [f"qnx-port-doctor: {root}",
           f"  {s['error']} error(s), {s['warning']} warning(s), {s['info']} info", ""]
    for f in _sorted(fs):
        out.append(f"{f.file}:{f.line}: {f.severity} [{f.rule}] {f.title}")
        out.append(f"    {f.text}")
        out.append(f"    fix: {f.fix}")
        if f.note:
            out.append(f"    note: {f.note}")
    return "\n".join(out) + "\n"


def render_markdown(fs, root):
    s = summary(fs)
    out = [f"# QNX portability report: `{root}`", "",
           f"**{s['error']}** errors, **{s['warning']}** warnings, **{s['info']}** info", "",
           "## By rule", "", "| Rule | Severity | Title | Count |", "|---|---|---|---|"]
    guarded = sum(1 for f in fs if f.note)
    if guarded:
        out[3:3] = ["", f"{guarded} finding(s) downgraded to info because the code is already conditional.", ""]
    by = Counter((f.rule, f.severity, f.title) for f in fs)
    for (r, sev, t), n in sorted(by.items(), key=lambda x: (ORDER[x[0][1]], x[0][0])):
        out.append(f"| {r} | {sev} | {t} | {n} |")
    out += ["", "## Findings", "", "| Location | Rule | Code | Suggested fix |", "|---|---|---|---|"]
    for f in _sorted(fs):
        code = f.text.replace("|", "\\|")
        fix = f.fix + (f" _({f.note})_" if f.note else "")
        out.append(f"| `{f.file}:{f.line}` | {f.rule} | `{code}` | {fix} |")
    return "\n".join(out) + "\n"


def render_json(fs, root):
    return json.dumps({"root": root, "summary": summary(fs),
                       "findings": [f.to_dict() for f in _sorted(fs)]}, indent=2) + "\n"


RENDERERS = {"text": render_text, "md": render_markdown, "markdown": render_markdown, "json": render_json}


_SARIF_LEVEL = {"error": "error", "warning": "warning", "info": "note"}


def render_sarif(fs, root, rules=None):
    """SARIF 2.1.0 (GitHub code scanning, VS Code SARIF viewer)."""
    from . import __version__
    from .rules import RULES
    rules = rules or RULES
    index = {r.id: i for i, r in enumerate(rules)}
    driver = {
        "name": "qnx-port-doctor", "version": __version__, "informationUri": "https://qnx.devpost.com/",
        "rules": [{
            "id": r.id, "name": r.id,
            "shortDescription": {"text": r.title},
            "help": {"text": r.fix},
            "defaultConfiguration": {"level": _SARIF_LEVEL[r.severity]},
            "properties": {"kind": r.kind, "autofix": bool(r.autofix)},
        } for r in rules],
    }
    results = []
    for f in _sorted(fs):
        msg = f"{f.title}. Fix: {f.fix}" + (f" ({f.note})" if f.note else "")
        res = {
            "ruleId": f.rule, "level": _SARIF_LEVEL[f.severity], "message": {"text": msg},
            "locations": [{"physicalLocation": {
                "artifactLocation": {"uri": f.file.replace("\\", "/"), "uriBaseId": "SRCROOT"},
                "region": {"startLine": f.line, "snippet": {"text": f.text}}}}],
        }
        if f.rule in index:
            res["ruleIndex"] = index[f.rule]
        results.append(res)
    doc = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json", "version": "2.1.0",
        "runs": [{"tool": {"driver": driver}, "results": results,
                  "originalUriBaseIds": {"SRCROOT": {"uri": "file://" + os.path.abspath(root).rstrip("/") + "/"}}}],
    }
    return json.dumps(doc, indent=2) + "\n"


RENDERERS["sarif"] = render_sarif
