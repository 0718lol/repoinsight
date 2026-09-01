"""Self-contained HTML report: one file, no server, no network assets."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Dict, List

from ..analyzer import RepoAnalyzer


_CSS = """
:root { --bg:#0f1420; --panel:#171e2e; --border:#26304a; --text:#dbe4f5;
        --muted:#8b98b8; --accent:#5b9dff; --good:#3ecf8e; --warn:#f5b453; --bad:#f26d6d; }
* { box-sizing: border-box; }
body { margin:0; font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
       background:var(--bg); color:var(--text); line-height:1.5; }
header { padding:28px 32px 18px; border-bottom:1px solid var(--border); }
header h1 { margin:0 0 4px; font-size:22px; }
header .sub { color:var(--muted); font-size:13px; }
main { max-width:1100px; margin:0 auto; padding:24px 32px 64px; }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:14px; margin:20px 0 32px; }
.card { background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:14px 16px; }
.card .num { font-size:26px; font-weight:700; color:var(--accent); }
.card .lbl { font-size:12px; color:var(--muted); margin-top:2px; }
h2 { font-size:16px; margin:34px 0 12px; color:var(--accent); }
table { width:100%; border-collapse:collapse; font-size:13px; }
th { text-align:left; color:var(--muted); font-weight:600; padding:6px 10px; border-bottom:1px solid var(--border); }
td { padding:6px 10px; border-bottom:1px solid var(--border); }
tr:hover td { background:rgba(91,157,255,.06); }
td.num { text-align:right; font-variant-numeric:tabular-nums; }
.bar { height:8px; border-radius:4px; background:linear-gradient(90deg,var(--accent),#7f6bff); }
.meter { position:relative; background:#232c44; border-radius:4px; height:8px; overflow:hidden; }
.meter > div { height:100%; }
.badge { display:inline-block; padding:1px 8px; border-radius:10px; font-size:11px; }
.b-critical { background:rgba(242,109,109,.15); color:var(--bad); }
.b-high { background:rgba(245,180,83,.15); color:var(--warn); }
.b-ok { background:rgba(62,207,142,.15); color:var(--good); }
.muted { color:var(--muted); }
.filepath { color:var(--muted); font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; }
#tabs { display:flex; gap:8px; margin:24px 0 0; }
#tabs button { background:var(--panel); color:var(--muted); border:1px solid var(--border);
       border-radius:8px 8px 0 0; padding:8px 18px; cursor:pointer; font-size:13px; }
#tabs button.active { color:var(--text); border-bottom-color:var(--bg); }
.tabpage { border:1px solid var(--border); border-radius:0 10px 10px 10px; padding:18px; background:var(--panel); }
.legend { font-size:12px; color:var(--muted); margin-top:10px; }
.dot-node { fill:#8fb6ff; stroke:none; }
svg text { fill:var(--text); font-size:11px; }
"""


def _severity(cx: int) -> str:
    if cx >= 15:
        return "b-critical"
    if cx >= 8:
        return "b-high"
    return "b-ok"


def _esc(v) -> str:
    return html.escape(str(v))


def _symbol_tree(symbols: List[Dict], files: List[str]) -> List[Dict]:
    """Group symbols per file for the explorer table."""
    by_file: Dict[str, List[Dict]] = {}
    for s in symbols:
        by_file.setdefault(s["file"], []).append(s)
    return [
        {"file": f, "symbols": sorted(syms, key=lambda x: x["line_start"])}
        for f, syms in sorted(by_file.items())
        if f in set(files)
    ]


def render_html_report(analyzer: RepoAnalyzer, path: str) -> str:
    s = analyzer.summary()
    files = analyzer.file_metrics()
    cx_rows = analyzer.complexity_report(top=40)
    coupling = analyzer.coupling_report()
    coupling_ranked = sorted(
        coupling.items(), key=lambda kv: -(kv[1]["fan_in"] + kv[1]["fan_out"])
    )[:40]
    symbol_groups = _symbol_tree(
        [sym.to_dict() for sym in analyzer.result.symbols],
        [f["path"] for f in files],
    )
    max_cx = max((r["complexity"] for r in cx_rows), default=1)
    max_code = max((f["code"] for f in files), default=1)

    parts: List[str] = []
    parts.append("<!DOCTYPE html><html><head><meta charset='utf-8'>")
    parts.append("<title>repoinsight report</title>")
    parts.append(f"<style>{_CSS}</style></head><body>")
    parts.append("<header><h1>repoinsight · 代码库分析报告</h1>")
    parts.append(f"<div class='sub'>{_esc(s['root'])}</div></header><main>")

    # --- summary cards -------------------------------------------------
    cards = [
        (s["files"], "文件总数"), (s["python_files"], "Python 文件"),
        (s["code_lines"], "代码行"), (s["symbols"], "符号总数"),
        (s["functions"], "函数/方法"), (s["module_dependencies"], "模块依赖边"),
        (s["call_edges"], "调用边"), (s["parse_errors"], "解析错误"),
    ]
    parts.append("<div class='cards'>")
    for num, lbl in cards:
        parts.append(f"<div class='card'><div class='num'>{num}</div><div class='lbl'>{lbl}</div></div>")
    parts.append("</div>")

    # --- tabs ----------------------------------------------------------
    parts.append("<div id='tabs'>")
    parts.append("<button class='active' data-tab='files'>文件</button>")
    parts.append("<button data-tab='complexity'>复杂度</button>")
    parts.append("<button data-tab='coupling'>耦合度</button>")
    parts.append("<button data-tab='symbols'>符号</button>")
    parts.append("<button data-tab='data'>原始数据</button>")
    parts.append("</div>")

    # files tab
    parts.append("<div class='tabpage' id='tab-files'><h2 style='margin-top:0'>按代码行数排序的文件</h2>")
    parts.append("<table><tr><th>文件</th><th>语言</th><th class='num'>代码</th><th class='num'>注释</th><th style='width:30%'></th></tr>")
    for f in files[:60]:
        pct = int(f["code"] / max_code * 100) if max_code else 0
        parts.append(
            f"<tr><td class='filepath'>{_esc(f['path'])}</td><td>{_esc(f['language'])}</td>"
            f"<td class='num'>{f['code']}</td><td class='num'>{f['comment']}</td>"
            f"<td><div class='meter'><div style='width:{pct}%'></div></div></td></tr>"
        )
    parts.append("</table></div>")

    # complexity tab
    parts.append("<div class='tabpage' id='tab-complexity' style='display:none'>"
                 "<h2 style='margin-top:0'>圈复杂度最高的函数</h2>")
    parts.append("<table><tr><th>复杂度</th><th>函数</th><th>位置</th><th style='width:22%'></th></tr>")
    for r in cx_rows:
        pct = int(r["complexity"] / max_cx * 100) if max_cx else 0
        parts.append(
            f"<tr><td class='num'><span class='badge {_severity(r['complexity'])}'>{r['complexity']}</span></td>"
            f"<td class='filepath'>{_esc(r['name'])}</td>"
            f"<td class='filepath'>{_esc(r['file'])}:{r['line']}</td>"
            f"<td><div class='meter'><div style='width:{pct}%'></div></div></td></tr>"
        )
    parts.append("</table>")
    parts.append("<div class='legend'>绿色 &lt; 8 · 橙色 8–14 · 红色 ≥ 15</div></div>")

    # coupling tab
    parts.append("<div class='tabpage' id='tab-coupling' style='display:none'>"
                 "<h2 style='margin-top:0'>模块耦合度(fan-in / fan-out)</h2>")
    parts.append("<table><tr><th>模块</th><th class='num'>被依赖(fan-in)</th><th class='num'>依赖(fan-out)</th></tr>")
    for mod, c in coupling_ranked:
        parts.append(
            f"<tr><td class='filepath'>{_esc(mod)}</td>"
            f"<td class='num'>{c['fan_in']}</td><td class='num'>{c['fan_out']}</td></tr>"
        )
    parts.append("</table></div>")

    # symbols tab
    parts.append("<div class='tabpage' id='tab-symbols' style='display:none'>"
                 "<h2 style='margin-top:0'>符号浏览器</h2>")
    for group in symbol_groups:
        parts.append(f"<h3 class='filepath' style='margin:18px 0 6px'>{_esc(group['file'])}</h3>")
        parts.append("<table>")
        for sym in group["symbols"]:
            parts.append(
                f"<tr><td style='width:110px'>{_esc(sym['kind'])}</td>"
                f"<td class='filepath'>{_esc(sym['qualified_name'])}</td>"
                f"<td class='num muted'>L{sym['line_start']}–{sym['line_end']}"
                + (f" · cx {sym['complexity']}" if sym["kind"] != "class" else "")
                + "</td></tr>"
            )
        parts.append("</table>")
    parts.append("</div>")

    # raw data tab
    payload = {
        "summary": s,
        "module_dependencies": analyzer.result.module_dependencies,
        "call_edges": [list(e) for e in analyzer.result.call_edges],
        "files": files,
    }
    parts.append("<div class='tabpage' id='tab-data' style='display:none'>"
                 "<h2 style='margin-top:0'>原始数据(JSON)</h2><pre style='overflow:auto;"
                 "max-height:70vh' class='filepath'>")
    parts.append(_esc(json.dumps(payload, indent=2, ensure_ascii=False)))
    parts.append("</pre></div>")

    parts.append("</main>")
    parts.append(
        "<script>"
        "document.querySelectorAll('#tabs button').forEach(function(b){"
        "b.addEventListener('click',function(){"
        "document.querySelectorAll('#tabs button').forEach(function(x){x.classList.remove('active')});"
        "b.classList.add('active');"
        "document.querySelectorAll('.tabpage').forEach(function(p){p.style.display='none'});"
        "document.getElementById('tab-'+b.dataset.tab).style.display='block';"
        "});});</script>"
    )
    parts.append("</body></html>")

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts), encoding="utf-8")
    return str(out)
