"""Interactive self-contained HTML report (no server, no network assets).

Python collects all data at render time, embeds it as one JSON blob and
inlines CSS/JS. The produced file works offline in any modern browser.
The force-directed graph is plain JS, no libraries.
"""

from __future__ import annotations

import html as _html
import json
from pathlib import Path
from typing import Dict, List

from ..analyzer import RepoAnalyzer

MAX_SOURCE_LINES = 500
MAX_CALL_NODES = 80


def esc(v) -> str:
    return _html.escape(str(v))


# ---------------------------------------------------------------------- #
def _collect_data(analyzer: RepoAnalyzer) -> Dict:
    result = analyzer.result
    modules = set(result.module_dependencies)
    for deps in result.module_dependencies.values():
        modules.update(deps)

    degree: Dict[str, int] = {}
    for a, b in result.call_edges:
        degree[a] = degree.get(a, 0) + 1
        degree[b] = degree.get(b, 0) + 1
    keep = {n for n, _ in sorted(degree.items(), key=lambda kv: -kv[1])[:MAX_CALL_NODES]}

    sources: Dict[str, List[str]] = {}
    for f in result.files:
        if f.language != "python":
            continue
        try:
            lines = Path(f.absolute_path).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        sources[f.path] = lines[:MAX_SOURCE_LINES]

    return {
        "summary": analyzer.summary(),
        "modules": sorted(modules),
        "moduleDeps": result.module_dependencies,
        "callEdges": [list(e) for e in result.call_edges if e[0] in keep and e[1] in keep],
        "files": analyzer.file_metrics(),
        "complexity": analyzer.complexity_report(top=40),
        "coupling": analyzer.coupling_report(),
        "symbols": [
            {
                "kind": s.kind, "name": s.name, "q": s.qualified_name,
                "file": s.file, "line": s.line_start,
                "end": s.line_end, "cx": s.complexity,
            }
            for s in result.symbols
        ],
        "sources": sources,
    }


# ---------------------------------------------------------------------- #
_CSS = """
:root{--bg:#0d1117;--panel:#161b27;--panel2:#1c2333;--border:#2a3450;--text:#e6edf7;
--muted:#93a1bd;--accent:#6aa6ff;--violet:#9d8cff;--good:#3ecf8e;--warn:#f0b453;
--bad:#f26d6d;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
font-family:-apple-system,'Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',sans-serif;line-height:1.55}
header{padding:22px 28px 16px;border-bottom:1px solid var(--border);display:flex;
align-items:baseline;gap:14px;flex-wrap:wrap}
header h1{margin:0;font-size:20px;letter-spacing:.3px}
header h1 em{color:var(--accent);font-style:normal}
header .root{color:var(--muted);font-size:12px;font-family:var(--mono)}
#search{margin-left:auto;background:var(--panel);border:1px solid var(--border);
color:var(--text);border-radius:8px;padding:7px 12px;font-size:13px;width:240px;outline:none}
#search:focus{border-color:var(--accent)}
main{max-width:1200px;margin:0 auto;padding:20px 28px 70px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:18px 0}
.card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:13px 16px}
.card .num{font-size:24px;font-weight:700;color:var(--accent)}
.card.bad .num{color:var(--bad)}
.card .lbl{font-size:12px;color:var(--muted)}
#tabs{display:flex;gap:6px;margin:26px 0 0;flex-wrap:wrap}
#tabs button{background:transparent;color:var(--muted);border:1px solid transparent;
border-radius:10px 10px 0 0;padding:9px 16px;cursor:pointer;font-size:13.5px}
#tabs button.active{background:var(--panel);color:var(--text);border-color:var(--border);border-bottom-color:var(--panel)}
.tabpage{display:none;border:1px solid var(--border);background:var(--panel);
border-radius:0 12px 12px 12px;padding:16px}
.tabpage.active{display:block}
h2{font-size:14.5px;margin:2px 0 12px;color:var(--muted);font-weight:600;letter-spacing:.4px;text-transform:uppercase}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:var(--muted);padding:6px 10px;border-bottom:1px solid var(--border);font-weight:600}
td{padding:6px 10px;border-bottom:1px solid rgba(42,52,80,.45)}
tr:hover td{background:rgba(106,166,255,.06)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.mono{font-family:var(--mono);font-size:12px}
.meter{height:7px;border-radius:4px;background:#232c44;overflow:hidden}
.meter>div{height:100%;background:linear-gradient(90deg,var(--accent),var(--violet))}
.badge{display:inline-block;padding:1px 9px;border-radius:10px;font-size:11px;font-weight:600}
.b-critical{background:rgba(242,109,109,.16);color:var(--bad)}
.b-high{background:rgba(240,180,83,.16);color:var(--warn)}
.b-ok{background:rgba(62,207,142,.16);color:var(--good)}
.graph{width:100%;height:560px;border:1px solid var(--border);border-radius:10px;
background:radial-gradient(1200px 500px at 50% -10%,rgba(24,32,51,0),#131a2a);cursor:grab;overflow:hidden}
.graph:active{cursor:grabbing}
.graph text{fill:var(--muted);font-size:10.5px;pointer-events:none;font-family:var(--mono)}
.graph line{stroke:#33405f;stroke-opacity:.75}
.graph line.hl{stroke:var(--accent);stroke-opacity:1;stroke-width:1.6}
.graph circle{fill:#5f8fe0;stroke:#0d1117;stroke-width:1.5;cursor:pointer}
.graph circle.hot{fill:var(--violet)}
.graph circle.dim{opacity:.15}
.graph line.dim{opacity:.06}
.graph circle.sel{stroke:var(--accent);stroke-width:2.5}
.detail{margin-top:10px;font-size:13px;color:var(--muted);min-height:40px}
.detail b{color:var(--text)}
.browser{display:grid;grid-template-columns:280px 1fr;gap:14px}
#filelist{border:1px solid var(--border);border-radius:10px;overflow:auto;max-height:560px;background:var(--panel2)}
#filelist div{padding:6px 12px;cursor:pointer;font-family:var(--mono);font-size:12px;
color:var(--muted);border-bottom:1px solid rgba(42,52,80,.4)}
#filelist div:hover{color:var(--text);background:rgba(106,166,255,.08)}
#filelist div.sel{color:var(--accent);background:rgba(106,166,255,.12)}
#srcwrap{border:1px solid var(--border);border-radius:10px;overflow:auto;max-height:520px;background:var(--panel2)}
pre.src{margin:0;font-family:var(--mono);font-size:12px;line-height:1.55;padding:10px 0}
pre.src .ln{display:inline-block;width:52px;text-align:right;padding-right:14px;color:#4a5878;user-select:none}
pre.src .lc{display:inline-block;width:calc(100% - 52px)}
pre.src .lc.on{background:rgba(106,166,255,.18)}
#symbox{margin-top:10px;display:flex;gap:6px;flex-wrap:wrap;min-height:26px}
#symbox span{background:var(--panel2);border:1px solid var(--border);border-radius:8px;
padding:3px 10px;font-size:11.5px;font-family:var(--mono);cursor:pointer;color:var(--muted)}
#symbox span:hover{color:var(--accent);border-color:var(--accent)}
"""

_JS = r"""
const DATA = JSON.parse(document.getElementById('ri-data').textContent);
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

/* ---------------- tabs (keys 1-5) ---------------- */
const tabs = [...document.querySelectorAll('#tabs button')];
function showTab(id){
  tabs.forEach(b => b.classList.toggle('active', b.dataset.tab === id));
  document.querySelectorAll('.tabpage').forEach(p => p.classList.toggle('active', p.id === 'tab-' + id));
  if (id === 'deps') drawGraph('deps');
  if (id === 'calls') drawGraph('calls');
}
tabs.forEach(b => b.onclick = () => showTab(b.dataset.tab));
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') return;
  const i = parseInt(e.key);
  if (i >= 1 && i <= tabs.length) showTab(tabs[i-1].dataset.tab);
});

/* ---------------- force-directed graph ---------------- */
const sims = {};
function drawGraph(kind){
  const svg = document.getElementById('svg-' + kind);
  const wrap = svg.closest('.graph');
  const W = wrap.clientWidth || 900, H = wrap.clientHeight || 560;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  if (!sims[kind]){
    const all = kind === 'deps' ? DATA.modules : uniqueNodes(DATA.callEdges);
    const edges = kind === 'deps'
      ? Object.entries(DATA.moduleDeps).flatMap(([s, ts]) => ts.map(t => [s, t]))
      : DATA.callEdges;
    const sim = { nodes: all.map(id => ({id, deg: 0})), byId: {}, edges, w: W, h: H };
    sim.edges.forEach(([a, b]) => { touch(sim, a).deg++; touch(sim, b).deg++; });
    sim.nodes.forEach(n => sim.byId[n.id] = n);
    layout(sim);
    simulate(sim, 300);
    sims[kind] = sim;
  }
  const sim = sims[kind];
  const ns = 'http://www.w3.org/2000/svg';
  svg.innerHTML = '';
  const g = document.createElementNS(ns, 'g');
  const edgeEls = [], nodeEls = [];
  sim.edges.forEach(([s, t]) => {
    const l = document.createElementNS(ns, 'line');
    l.dataset.s = s; l.dataset.t = t;
    g.appendChild(l); edgeEls.push(l);
  });
  sim.nodes.forEach(n => {
    const c = document.createElementNS(ns, 'circle');
    c.setAttribute('r', 5 + Math.min(9, n.deg));
    if (n.deg > 4) c.classList.add('hot');
    c.dataset.id = n.id;
    const label = document.createElementNS(ns, 'text');
    n._circle = c; n._label = label;
    g.appendChild(c); g.appendChild(label); nodeEls.push(c);
  });
  svg.appendChild(g);
  const render = () => {
    edgeEls.forEach(l => {
      const a = sim.byId[l.dataset.s], b = sim.byId[l.dataset.t];
      l.setAttribute('x1', a.x); l.setAttribute('y1', a.y);
      l.setAttribute('x2', b.x); l.setAttribute('y2', b.y);
    });
    sim.nodes.forEach(n => {
      n._circle.setAttribute('cx', n.x); n._circle.setAttribute('cy', n.y);
      n._label.setAttribute('x', n.x + 11); n._label.setAttribute('y', n.y + 3.5);
      n._label.textContent = n.id;
    });
  };
  render();
  /* pan + zoom */
  let scale = 1, tx = 0, ty = 0, panning = false, px = 0, py = 0;
  const apply = () => g.setAttribute('transform', `translate(${tx},${ty}) scale(${scale})`);
  svg.onwheel = e => {
    e.preventDefault();
    scale = Math.max(0.2, Math.min(6, scale * (e.deltaY < 0 ? 1.12 : 0.89)));
    apply();
  };
  svg.onmousedown = e => { panning = true; px = e.clientX; py = e.clientY; };
  window.addEventListener('mouseup', () => panning = false);
  window.addEventListener('mousemove', e => {
    if (!panning) return;
    tx += e.clientX - px; ty += e.clientY - py; px = e.clientX; py = e.clientY; apply();
  });
  /* hover highlight + click detail */
  const detail = document.getElementById('detail-' + kind);
  nodeEls.forEach(c => {
    c.onmouseenter = () => {
      const id = c.dataset.id;
      edgeEls.forEach(l => l.classList.toggle('hl', l.dataset.s === id || l.dataset.t === id));
    };
    c.onmouseleave = () => edgeEls.forEach(l => l.classList.remove('hl'));
    c.onclick = () => {
      nodeEls.forEach(x => x.classList.remove('sel'));
      c.classList.add('sel');
      detail.innerHTML = kind === 'deps' ? depsDetail(c.dataset.id) : callsDetail(c.dataset.id);
    };
  });
}
function touch(sim, id){
  let n = sim.byId[id];
  if (!n){ n = {id, deg: 0}; sim.nodes.push(n); sim.byId[id] = n; }
  return n;
}
function uniqueNodes(edges){
  const s = new Set();
  edges.forEach(([a, b]) => { s.add(a); s.add(b); });
  return [...s];
}
function layout(sim){
  const groups = {};
  sim.nodes.forEach(n => {
    const top = n.id.split(/[.\/]/)[0];
    (groups[top] = groups[top] || []).push(n);
  });
  const tops = Object.keys(groups);
  tops.forEach((t, ti) => {
    const members = groups[t];
    const base = (ti / tops.length) * 2 * Math.PI;
    members.forEach((n, mi) => {
      const a = base + (mi / members.length) * 1.6;
      const r = members.length > 1 ? 130 : 0;
      n.x = sim.w / 2 + Math.cos(a) * (r + (ti % 3) * 70);
      n.y = sim.h / 2 + Math.sin(a) * (r + (ti % 3) * 45);
      n.vx = 0; n.vy = 0;
    });
  });
}
function simulate(sim, ticks){
  const {nodes, byId, edges, w, h} = sim;
  for (let t = 0; t < ticks; t++){
    for (let i = 0; i < nodes.length; i++){
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j++){
        const b = nodes[j];
        let dx = a.x - b.x, dy = a.y - b.y;
        const d2 = dx * dx + dy * dy || 0.01;
        const d = Math.sqrt(d2);
        const f = 2200 / d2;
        dx /= d; dy /= d;
        a.vx += dx * f; a.vy += dy * f;
        b.vx -= dx * f; b.vy -= dy * f;
      }
      a.vx += (w / 2 - a.x) * 0.004;
      a.vy += (h / 2 - a.y) * 0.004;
    }
    edges.forEach(([s, t]) => {
      const a = byId[s], b = byId[t];
      let dx = b.x - a.x, dy = b.y - a.y;
      const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const push = (d - 95) * 0.02;
      dx /= d; dy /= d;
      a.vx += dx * push; a.vy += dy * push;
      b.vx -= dx * push; b.vy -= dy * push;
    });
    nodes.forEach(n => {
      n.vx *= 0.82; n.vy *= 0.82;
      n.x = Math.max(30, Math.min(w - 30, n.x + n.vx));
      n.y = Math.max(24, Math.min(h - 24, n.y + n.vy));
    });
  }
}
function depsDetail(id){
  const outs = DATA.moduleDeps[id] || [];
  const ins = Object.entries(DATA.moduleDeps).filter(([, ts]) => ts.includes(id)).map(([m]) => m);
  return `<b>${esc(id)}</b> · 被依赖 ${ins.length} · 依赖 ${outs.length}`
    + `<br>依赖 → ${outs.map(esc).join(', ') || '—'}`
    + `<br>被依赖 ← ${ins.map(esc).join(', ') || '—'}`;
}
function callsDetail(id){
  const outs = DATA.callEdges.filter(([a]) => a === id).map(([, b]) => b);
  const ins = DATA.callEdges.filter(([, b]) => b === id).map(([a]) => a);
  return `<b>${esc(id)}</b> · 调用 ${outs.length} · 被调用 ${ins.length}`
    + `<br>→ ${outs.map(esc).join(', ') || '—'}`
    + `<br>← ${ins.map(esc).join(', ') || '—'}`;
}

/* ---------------- source browser ---------------- */
const fileList = document.getElementById('filelist');
const srcWrap = document.getElementById('srcwrap');
const symBox = document.getElementById('symbox');
const symsByFile = {};
DATA.symbols.forEach(s => { (symsByFile[s.file] = symsByFile[s.file] || []).push(s); });
function openFile(path, line){
  [...fileList.children].forEach(c => c.classList.toggle('sel', c.dataset.path === path));
  const lines = DATA.sources[path] || [];
  let body = '';
  lines.forEach((l, i) => {
    const on = (line && i + 1 === line) ? ' on' : '';
    body += `<span class="ln">${i + 1}</span><span class="lc${on}">${esc(l) || ' '}</span>\n`;
  });
  srcWrap.innerHTML = `<pre class="src">${body}</pre>`;
  symBox.innerHTML = '';
  (symsByFile[path] || []).forEach(s => {
    const el = document.createElement('span');
    el.textContent = `${s.kind}  ${s.name}`;
    el.title = `L${s.line}${s.kind !== 'class' ? ' · cx ' + s.cx : ''}`;
    el.onclick = () => openFile(path, s.line);
    symBox.appendChild(el);
  });
  if (line){
    const target = srcWrap.querySelector('.lc.on');
    if (target) target.scrollIntoView({block: 'center'});
  } else {
    srcWrap.scrollTop = 0;
  }
}
DATA.files.filter(f => DATA.sources[f.path]).forEach(f => {
  const d = document.createElement('div');
  d.textContent = f.path;
  d.dataset.path = f.path;
  d.onclick = () => openFile(f.path);
  fileList.appendChild(d);
});
if (fileList.firstChild) openFile(fileList.firstChild.dataset.path);

/* ---------------- global search ---------------- */
document.getElementById('search').addEventListener('input', e => {
  const q = e.target.value.toLowerCase();
  document.querySelectorAll('.graph circle').forEach(c => {
    c.classList.toggle('dim', !!q && !c.dataset.id.toLowerCase().includes(q));
  });
  document.querySelectorAll('#filelist div').forEach(d => {
    d.style.display = (!q || d.dataset.path.toLowerCase().includes(q)) ? '' : 'none';
  });
});
"""


def render_interactive_report(analyzer: RepoAnalyzer, path: str) -> str:
    data = _collect_data(analyzer)
    s = data["summary"]

    cards = [
        (s["files"], "文件总数", ""),
        (s["python_files"], "Python 文件", ""),
        (s["code_lines"], "代码行", ""),
        (s["functions"], "函数/方法", ""),
        (s["module_dependencies"], "模块依赖边", ""),
        (s["call_edges"], "调用边", ""),
        (s["parse_errors"], "解析错误", "bad" if s["parse_errors"] else ""),
    ]
    card_html = "".join(
        f"<div class='card {cls}'><div class='num'>{n}</div><div class='lbl'>{lbl}</div></div>"
        for n, lbl, cls in cards
    )

    max_cx = max((r["complexity"] for r in data["complexity"]), default=1)
    cx_rows = ""
    for r in data["complexity"]:
        cx = r["complexity"]
        badge = "b-critical" if cx >= 15 else ("b-high" if cx >= 8 else "b-ok")
        pct = int(cx / max_cx * 100)
        cx_rows += (
            f"<tr><td class='num'><span class='badge {badge}'>{cx}</span></td>"
            f"<td class='mono'>{esc(r['name'])}</td>"
            f"<td class='mono'>{esc(r['file'])}:{r['line']}</td>"
            f"<td><div class='meter'><div style='width:{pct}%'></div></div></td></tr>"
        )

    coupling_rows = ""
    ranked = sorted(
        data["coupling"].items(), key=lambda kv: -(kv[1]["fan_in"] + kv[1]["fan_out"])
    )[:40]
    for mod, c in ranked:
        coupling_rows += (
            f"<tr><td class='mono'>{esc(mod)}</td>"
            f"<td class='num'>{c['fan_in']}</td><td class='num'>{c['fan_out']}</td></tr>"
        )

    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    page = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>repoinsight 交互报告</title>
<style>{_CSS}</style>
</head><body>
<header>
  <h1><em>repoinsight</em> 代码库交互报告</h1>
  <span class="root">{esc(s['root'])}</span>
  <input id="search" placeholder="搜索模块 / 文件…（高亮过滤）" autocomplete="off">
</header>
<main>
  <div class="cards">{card_html}</div>
  <div id="tabs">
    <button class="active" data-tab="deps">① 模块依赖图</button>
    <button data-tab="calls">② 调用图</button>
    <button data-tab="src">③ 源码浏览</button>
    <button data-tab="cx">④ 复杂度</button>
    <button data-tab="coupling">⑤ 耦合度</button>
  </div>

  <div class="tabpage active" id="tab-deps">
    <h2>模块依赖 · 拖动节点 / 滚轮缩放 / 点击节点看详情 / 键盘 1-5 切页</h2>
    <div class="graph"><svg id="svg-deps" width="100%" height="100%"></svg></div>
    <div class="detail" id="detail-deps">悬停高亮连线，点击节点查看依赖关系。</div>
  </div>

  <div class="tabpage" id="tab-calls">
    <h2>调用图（最活跃的 {len(data['callEdges'])} 条调用边）</h2>
    <div class="graph"><svg id="svg-calls" width="100%" height="100%"></svg></div>
    <div class="detail" id="detail-calls">悬停高亮连线，点击节点查看调用者/被调用者。</div>
  </div>

  <div class="tabpage" id="tab-src">
    <h2>源码浏览器 · 左侧选文件，下方符号可点击跳转</h2>
    <div class="browser">
      <div id="filelist"></div>
      <div>
        <div id="srcwrap"></div>
        <div id="symbox"></div>
      </div>
    </div>
  </div>

  <div class="tabpage" id="tab-cx">
    <h2>圈复杂度 Top 40（≥15 红 / 8–14 橙 / &lt;8 绿）</h2>
    <table><tr><th class="num">复杂度</th><th>函数</th><th>位置</th><th style="width:24%"></th></tr>
    {cx_rows}</table>
  </div>

  <div class="tabpage" id="tab-coupling">
    <h2>模块耦合度</h2>
    <table><tr><th>模块</th><th class="num">被依赖 fan-in</th><th class="num">依赖 fan-out</th></tr>
    {coupling_rows}</table>
  </div>
</main>
<script id="ri-data" type="application/json">{data_json}</script>
<script>{_JS}</script>
</body></html>"""

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return str(out)
