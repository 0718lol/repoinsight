"""Interactive self-contained HTML report, cockpit style (v3).

Single output file, works offline: Python embeds all data as JSON and
inlines CSS/JS. Visual features: animated KPI counters, glowing
force-directed graphs with flowing edges, donut charts, a file heatmap,
and syntax-highlighted source browser. No external assets at all.
"""

from __future__ import annotations

import html as _html
from pathlib import Path

from ..analyzer import RepoAnalyzer
from .interactive_data import collect_data
from .interactive_template import render_page


def esc(v) -> str:
    return _html.escape(str(v), quote=False)


# ---------------------------------------------------------------------- #
_collect_data = collect_data


# ---------------------------------------------------------------------- #
_CSS = r"""
:root{--bg:#070a12;--bg2:#0b101d;--panel:rgba(22,28,44,.72);--border:#242f4d;
--text:#e8eefb;--muted:#8d9bbd;--accent:#6aa6ff;--violet:#a08cff;--good:#3ecf8e;
--warn:#f0b453;--bad:#f26d6d;--cyan:#4fd6d2;--pink:#e87bb0;
--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:
 radial-gradient(900px 480px at 85% -80px,rgba(160,140,255,.14),transparent),
 radial-gradient(1100px 520px at 8% -120px,rgba(106,166,255,.12),transparent),
 var(--bg);
 color:var(--text);min-height:100vh;
 font-family:-apple-system,'Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',sans-serif;
 line-height:1.55}
::selection{background:rgba(106,166,255,.35)}

header{padding:34px 34px 10px;max-width:1280px;margin:0 auto}
.brand{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
.brand h1{margin:0;font-size:30px;font-weight:800;letter-spacing:.5px;
 background:linear-gradient(92deg,#8fb8ff 0%,#a08cff 55%,#4fd6d2 100%);
 -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
.brand .tag{color:var(--muted);font-size:12.5px;border:1px solid var(--border);
 padding:3px 12px;border-radius:999px;background:var(--panel)}
.brand .root{color:var(--muted);font-size:12px;font-family:var(--mono);width:100%;
 margin-left:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#search{margin-left:auto;background:rgba(10,15,28,.8);border:1px solid var(--border);
 color:var(--text);border-radius:10px;padding:9px 14px;font-size:13.5px;width:250px;outline:none;
 transition:border-color .2s, box-shadow .2s}
#search:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(106,166,255,.18)}
#search::placeholder{color:#5a688c}

main{max-width:1280px;margin:0 auto;padding:14px 34px 80px}

/* ---- KPI cards ---- */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin:22px 0 6px}
.card{position:relative;background:var(--panel);backdrop-filter:blur(8px);
 border:1px solid var(--border);border-radius:16px;padding:16px 18px 14px;overflow:hidden;
 transition:transform .18s, border-color .18s}
.card:hover{transform:translateY(-3px);border-color:#3a4a78}
.card::after{content:'';position:absolute;inset:0 0 auto 0;height:2px;
 background:linear-gradient(90deg,transparent,var(--ac,var(--accent)),transparent);opacity:.7}
.card .num{font-size:30px;font-weight:800;font-variant-numeric:tabular-nums;
 color:var(--ac,var(--accent));text-shadow:0 0 22px color-mix(in srgb,var(--ac,var(--accent)) 45%,transparent)}
.card .lbl{font-size:12px;color:var(--muted);margin-top:2px;letter-spacing:.5px}

/* ---- tabs ---- */
#tabs{display:flex;gap:6px;margin:30px 0 0;flex-wrap:wrap}
#tabs button{background:transparent;color:var(--muted);border:1px solid transparent;
 border-radius:12px 12px 0 0;padding:10px 18px;cursor:pointer;font-size:13.5px;
 transition:color .15s}
#tabs button:hover{color:var(--text)}
#tabs button.active{background:var(--panel);color:var(--text);border-color:var(--border);
 border-bottom-color:transparent;position:relative;z-index:1}
.tabpage{display:none;border:1px solid var(--border);background:var(--panel);
 backdrop-filter:blur(8px);border-radius:0 16px 16px 16px;padding:18px}
.tabpage.active{display:block;animation:fadein .25s ease}
@keyframes fadein{from{opacity:0;transform:translateY(4px)}to{opacity:1}}
h2{font-size:12.5px;margin:2px 0 14px;color:var(--muted);font-weight:600;
 letter-spacing:1.2px;text-transform:uppercase;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
h2 .hint{font-weight:400;letter-spacing:.2px;text-transform:none;opacity:.75}

/* ---- overview ---- */
.overview{display:grid;grid-template-columns:minmax(220px,.7fr) 1.3fr;gap:14px}
.overview-score,.overview-panel{background:rgba(10,15,28,.5);border:1px solid var(--border);border-radius:14px;padding:20px}
.overview-score{display:flex;align-items:center;gap:18px;min-height:190px}
.overview-score strong{font-size:54px;line-height:1;color:var(--accent);font-variant-numeric:tabular-nums}
.overview-score .grade{font-size:14px;color:var(--muted);margin-top:8px}
.overview-score .caption{font-size:12px;color:var(--muted);margin-top:14px}
.overview-panel h3{margin:0 0 12px;font-size:14px;color:var(--text)}
.overview-panel p{margin:0;color:var(--muted);font-size:13px}
.overview-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}
.overview-actions button{background:rgba(106,166,255,.1);color:#a9c6ff;border:1px solid rgba(106,166,255,.3);
 border-radius:8px;padding:8px 12px;cursor:pointer;font-size:12.5px}
.overview-actions button:hover{border-color:var(--accent);color:var(--text)}
.signals{display:grid;gap:8px;margin-top:12px}
.signal{display:flex;align-items:flex-start;gap:10px;padding:9px 10px;border:1px solid var(--border);border-radius:8px;font-size:12.5px}
.signal .mark{font-weight:800;min-width:42px}.signal.ok .mark{color:var(--good)}
.signal.warn .mark{color:var(--warn)}.signal.bad .mark{color:var(--bad)}
.signal .copy{color:var(--muted)}.signal .copy b{color:var(--text);font-weight:600}

/* ---- graphs ---- */
.graph{position:relative;width:100%;height:600px;border:1px solid var(--border);
 border-radius:14px;overflow:hidden;
 background:radial-gradient(700px 340px at 50% 0%,rgba(38,50,86,.5),rgba(9,13,24,.4))}
.graph svg{width:100%;height:100%}
.graph text{fill:var(--muted);font-size:10.5px;pointer-events:none;font-family:var(--mono)}
.graph text.big{fill:#c9d6f2;font-size:11.5px}
.graph line{stroke:#31405f;stroke-opacity:.55;fill:none}
.graph path.edge{stroke:#31405f;stroke-opacity:.45;fill:none}
.graph path.edge.flow{stroke:var(--accent);stroke-opacity:1;stroke-width:1.7;
 stroke-dasharray:7 5;animation:flow 1.1s linear infinite}
@keyframes flow{to{stroke-dashoffset:-24}}
.graph circle{cursor:pointer;transition:r .15s}
.graph circle.dim{opacity:.12}
.graph path.dim{opacity:.05}
.graph circle.sel{stroke-width:3}
.glowbtn{background:rgba(10,15,28,.7);color:var(--muted);border:1px solid var(--border);
 border-radius:8px;padding:4px 12px;font-size:12px;cursor:pointer}
.glowbtn:hover{color:var(--text);border-color:var(--accent)}
.detail{margin-top:12px;font-size:13px;color:var(--muted);min-height:44px;
 background:rgba(10,15,28,.5);border:1px solid var(--border);border-radius:10px;padding:10px 14px}
.detail b{color:var(--text)} .detail .chips{margin-top:4px;display:flex;gap:6px;flex-wrap:wrap}
.detail .chips span{background:rgba(106,166,255,.1);border:1px solid rgba(106,166,255,.25);
 color:#a9c6ff;border-radius:6px;padding:1px 8px;font-size:11.5px;font-family:var(--mono);cursor:pointer}
.legend{display:flex;gap:14px;margin-top:10px;font-size:12px;color:var(--muted);flex-wrap:wrap}
.legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px}

/* ---- charts row ---- */
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin-top:14px}
.chartbox{background:rgba(10,15,28,.5);border:1px solid var(--border);border-radius:14px;padding:16px}
.chartbox h3{margin:0 0 10px;font-size:13px;color:var(--muted);font-weight:600}
.donutwrap{display:flex;align-items:center;gap:18px;flex-wrap:wrap}
.dlegend{font-size:12.5px;color:var(--muted);display:grid;gap:6px}
.dlegend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:7px}
.dlegend b{color:var(--text);font-weight:600}

/* ---- heatmap ---- */
.heat{display:grid;grid-template-columns:repeat(auto-fill,minmax(14px,1fr));gap:3px;margin-top:8px}
.heat .cell{aspect-ratio:1;border-radius:3px;background:#1a2338;cursor:pointer;transition:transform .1s}
.heat .cell:hover{transform:scale(1.35);outline:1px solid var(--accent)}
.heatwrap{margin-top:4px;font-size:11.5px;color:var(--muted);font-family:var(--mono);min-height:18px}

/* ---- tables ---- */
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:var(--muted);padding:7px 10px;border-bottom:1px solid var(--border);font-weight:600}
td{padding:7px 10px;border-bottom:1px solid rgba(36,47,77,.5)}
tr:hover td{background:rgba(106,166,255,.05)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.mono{font-family:var(--mono);font-size:12px}
.meter{height:7px;border-radius:4px;background:#1a2338;overflow:hidden}
.meter>div{height:100%;border-radius:4px;
 background:linear-gradient(90deg,var(--accent),var(--violet))}
.badge{display:inline-block;padding:1px 10px;border-radius:999px;font-size:11px;font-weight:700}
.b-critical{background:rgba(242,109,109,.15);color:var(--bad);box-shadow:0 0 12px rgba(242,109,109,.25)}
.b-high{background:rgba(240,180,83,.15);color:var(--warn)}
.b-ok{background:rgba(62,207,142,.15);color:var(--good)}
/* health score */
#scorechip{display:flex;align-items:center;gap:12px;background:var(--panel);
border:1px solid var(--border);border-radius:14px;padding:8px 16px 8px 8px;margin-left:18px}
#scorechip svg{display:block}
#scorechip .sc{font-size:24px;font-weight:800;line-height:1}
#scorechip .sc-lbl{font-size:11.5px;color:var(--muted);margin-top:3px}
.g-good{color:var(--good)} .g-ok{color:var(--accent)} .g-warn{color:var(--warn)} .g-bad{color:var(--bad)}
.dimrow{display:flex;align-items:center;gap:10px;margin:7px 0;font-size:12.5px}
.dimrow .dn{width:80px;color:var(--muted);flex-shrink:0}
.dimrow .dm{flex:1}
.dimrow .dv{width:150px;color:var(--muted);font-size:11.5px;text-align:right;flex-shrink:0;
overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dimrow .dp{width:44px;text-align:right;font-weight:700;flex-shrink:0}

/* ---- source browser ---- */
.browser{display:grid;grid-template-columns:300px 1fr;gap:14px}
#filelist{border:1px solid var(--border);border-radius:12px;overflow:auto;max-height:600px;
 background:rgba(10,15,28,.5)}
#filelist div{padding:6px 13px;cursor:pointer;font-family:var(--mono);font-size:12px;
 color:var(--muted);border-bottom:1px solid rgba(36,47,77,.4);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#filelist div:hover{color:var(--text);background:rgba(106,166,255,.08)}
#filelist div.sel{color:var(--accent);background:rgba(106,166,255,.13);
 box-shadow:inset 2px 0 0 var(--accent)}
#srcwrap{border:1px solid var(--border);border-radius:12px;overflow:auto;max-height:560px;
 background:rgba(10,15,28,.55)}
pre.src{margin:0;font-family:var(--mono);font-size:12.5px;line-height:1.6;padding:12px 0}
pre.src .ln{display:inline-block;width:56px;text-align:right;padding-right:16px;color:#43507a;user-select:none}
pre.src .lc{display:inline-block;width:calc(100% - 56px);border-radius:3px}
pre.src .lc.on{background:rgba(106,166,255,.2);box-shadow:inset 2px 0 0 var(--accent)}
/* syntax colors */
.tk-c{color:#5f6f96;font-style:italic}
.tk-s{color:#9adf9f}
.tk-k{color:#7aa2ff;font-weight:600}
.tk-d{color:#e8a0ff}
.tk-n{color:#f0b453}
.tk-f{color:#4fd6d2}
#symbox{margin-top:10px;display:flex;gap:6px;flex-wrap:wrap;max-height:76px;overflow:auto}
#symbox span{background:rgba(10,15,28,.6);border:1px solid var(--border);border-radius:8px;
 padding:3px 11px;font-size:11.5px;font-family:var(--mono);cursor:pointer;color:var(--muted);
 transition:color .12s,border-color .12s}
#symbox span:hover{color:var(--accent);border-color:var(--accent)}

footer{max-width:1280px;margin:0 auto;padding:0 34px 40px;color:#4a5878;font-size:12px}
@media (max-width:720px){
 header{padding:22px 16px 8px}.brand{gap:9px}.brand h1{font-size:24px}
 #scorechip{order:3;margin-left:0}.brand .root{order:4}#search{order:5;width:100%;margin:6px 0 0}
 main{padding:10px 16px 52px}.cards{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.card{padding:12px}.card .num{font-size:23px}
 #tabs{margin-top:20px;gap:4px;overflow-x:auto;flex-wrap:nowrap;padding-bottom:1px}
 #tabs button{white-space:nowrap;padding:9px 12px;font-size:12px}.tabpage{padding:12px;border-radius:0 10px 10px 10px}
 .overview{grid-template-columns:1fr}.overview-score{min-height:150px;padding:16px}.overview-score strong{font-size:46px}
 .graph{height:420px}.browser{grid-template-columns:1fr}.browser #filelist{max-height:180px}
 .charts{grid-template-columns:1fr}.chartbox[style*="grid-column"]{grid-column:auto!important}
 table{display:block;overflow-x:auto;white-space:nowrap}.dimrow .dv{display:none}.dimrow .dn{width:76px}
 footer{padding:0 16px 28px}
}
"""

_JS = r"""
const DATA = JSON.parse(document.getElementById('ri-data').textContent);
const esc = s => String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const PALETTE = ['#6aa6ff','#a08cff','#3ecf8e','#f0b453','#e87bb0','#4fd6d2','#f26d6d','#8fd06a'];
const pkgColor = (()=>{ const m={}; let i=0;
  return pkg => (m[pkg] = m[pkg] ?? PALETTE[i++ % PALETTE.length]); })();
const pkgOf = id => id.split(/[.\/]/)[0];

/* ---- animated KPI counters ---- */
document.querySelectorAll('.card .num').forEach(el=>{
  const target = parseInt(el.dataset.v, 10) || 0;
  const t0 = performance.now(), dur = 900;
  const step = now => {
    const p = Math.min(1, (now - t0) / dur);
    el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3))).toLocaleString();
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
});

/* ---- tabs (keys 1-7) ---- */
const tabs = [...document.querySelectorAll('#tabs button')];
function showTab(id){
  tabs.forEach(b => {
    const active = b.dataset.tab === id;
    b.classList.toggle('active', active);
    b.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  document.querySelectorAll('.tabpage').forEach(p => {
    const active = p.id === 'tab-' + id;
    p.classList.toggle('active', active);
    p.setAttribute('aria-hidden', active ? 'false' : 'true');
  });
  if (id === 'overview') drawOverview();
  if (id === 'deps') drawGraph('deps');
  if (id === 'calls') drawGraph('calls');
  if (id === 'charts') drawCharts();
}
tabs.forEach(b => b.onclick = () => showTab(b.dataset.tab));
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') return;
  const i = parseInt(e.key);
  if (i >= 1 && i <= tabs.length) showTab(tabs[i-1].dataset.tab);
});

function drawOverview(){
  const h = DATA.health;
  const color = GRADE_COLOR[h.grade_class] || '#6aa6ff';
  const score = document.getElementById('overview-score');
  score.innerHTML = `<strong style="color:${color}">${h.total}</strong><div><div class="grade">${esc(h.grade)} · 架构健康分</div><div class="caption">分数越高，结构性风险越少</div></div>`;
  const risk = document.getElementById('overview-signals');
  const risky = h.dimensions.filter(d => d.penalty > 0);
  risk.innerHTML = risky.length ? risky.map(d => {
    const level = d.penalty >= d.max_penalty * .6 ? 'bad' : 'warn';
    return `<div class="signal ${level}"><span class="mark">-${d.penalty} 分</span><span class="copy"><b>${esc(d.name)}</b>：${esc(d.detail)}</span></div>`;
  }).join('') : '<div class="signal ok"><span class="mark">通过</span><span class="copy"><b>未发现结构性风险</b>：可以继续查看依赖图和复杂度明细。</span></div>';
}
document.querySelectorAll('[data-jump]').forEach(b => b.onclick = () => showTab(b.dataset.jump));

/* ---- force graph (shared engine) ---- */
const sims = {};
const showAllLabels = document.getElementById('show-labels');
showAllLabels.onchange = () => ['deps', 'calls'].forEach(k => { if (sims[k]) drawGraph(k); });
function drawGraph(kind){
  const svg = document.getElementById('svg-' + kind);
  const wrap = svg.closest('.graph');
  const W = wrap.clientWidth || 900, H = wrap.clientHeight || 600;
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
    simulate(sim, 320);
    sims[kind] = sim;
  }
  const sim = sims[kind];
  const ns = 'http://www.w3.org/2000/svg';
  svg.innerHTML =
    `<defs><filter id="glow-${kind}" x="-60%" y="-60%" width="220%" height="220%">`+
    `<feGaussianBlur stdDeviation="3.2" result="b"/>`+
    `<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>`;
  const g = document.createElementNS(ns, 'g');
  const edgeEls = [], nodeEls = [];
  sim.edges.forEach(([s, t]) => {
    const p = document.createElementNS(ns, 'path');
    p.setAttribute('class', 'edge');
    p.dataset.s = s; p.dataset.t = t;
    g.appendChild(p); edgeEls.push(p);
  });
  sim.nodes.forEach(n => {
    const c = document.createElementNS(ns, 'circle');
    c.setAttribute('r', 6 + Math.min(10, n.deg));
    c.dataset.id = n.id;
    c.dataset.pkg = pkgOf(n.id);
    const label = document.createElementNS(ns, 'text');
    n._circle = c; n._label = label;
    g.appendChild(c); g.appendChild(label); nodeEls.push(c);
  });
  svg.appendChild(g);
  const path = (a,b)=>{
    const mx=(a.x+b.x)/2, my=(a.y+b.y)/2;
    const dx=b.x-a.x, dy=b.y-a.y, len=Math.sqrt(dx*dx+dy*dy)||1;
    const ox=-dy/len*len*0.12, oy=dx/len*len*0.12;
    return `M${a.x},${a.y} Q${mx+ox},${my+oy} ${b.x},${b.y}`;
  };
  const render = () => {
    edgeEls.forEach(l => l.setAttribute('d', path(sim.byId[l.dataset.s], sim.byId[l.dataset.t])));
    sim.nodes.forEach(n => {
      n._circle.setAttribute('cx', n.x); n._circle.setAttribute('cy', n.y);
      n._circle.setAttribute('fill', pkgColor(pkgOf(n.id)));
      n._circle.setAttribute('filter', n.deg > 4 ? `url(#glow-${kind})` : '');
      n._label.setAttribute('x', n.x + 12); n._label.setAttribute('y', n.y + 3.5);
      n._label.textContent = showAllLabels.checked || n.deg > 3 ? n.id : '';
      n._label.classList.toggle('big', n.deg > 3);
    });
  };
  render();
  /* pan + zoom */
  let scale = 1, tx = 0, ty = 0, panning = false, px = 0, py = 0;
  const apply = () => g.setAttribute('transform', `translate(${tx},${ty}) scale(${scale})`);
  svg.onwheel = e => {
    e.preventDefault();
    scale = Math.max(0.15, Math.min(6, scale * (e.deltaY < 0 ? 1.13 : 0.885)));
    apply();
  };
  svg.onmousedown = e => { panning = true; px = e.clientX; py = e.clientY; };
  window.addEventListener('mouseup', () => panning = false);
  window.addEventListener('mousemove', e => {
    if (!panning) return;
    tx += e.clientX - px; ty += e.clientY - py; px = e.clientX; py = e.clientY; apply();
  });
  /* hover + click */
  const detail = document.getElementById('detail-' + kind);
  nodeEls.forEach(c => {
    c.onmouseenter = () => {
      const id = c.dataset.id;
      edgeEls.forEach(l => l.classList.toggle('flow', l.dataset.s === id || l.dataset.t === id));
    };
    c.onmouseleave = () => edgeEls.forEach(l => l.classList.remove('flow'));
    c.onclick = () => {
      nodeEls.forEach(x => x.classList.remove('sel'));
      c.classList.add('sel');
      c.setAttribute('stroke', '#ffffff');
      c.setAttribute('stroke-width', '2.5');
      detail.innerHTML = kind === 'deps' ? depsDetail(c.dataset.id) : callsDetail(c.dataset.id);
      detail.querySelectorAll('.chips span').forEach(ch => {
        ch.onclick = () => jumpToSymbol(ch.dataset.q);
      });
    };
  });
  render();
  /* package legend + big-repo notice for the deps graph */
  if (kind === 'deps'){
    const pkgs = [...new Set(sim.nodes.map(n => pkgOf(n.id)))];
    document.getElementById('legend-deps').innerHTML = pkgs.map(p =>
      `<span><i style="background:${pkgColor(p)}"></i>${esc(p)}</span>`).join('');
    if (DATA.graphMode === 'package'){
      document.getElementById('detail-deps').innerHTML =
        '⚠ 该仓库模块较多,依赖图已按<b>顶层包</b>聚合展示(滚动缩放查看)。' +
        '悬停/点击节点查看包级依赖。';
    }
  }
}
function touch(sim, id){
  let n = sim.byId[id];
  if (!n){ n = {id, deg: 0}; sim.nodes.push(n); sim.byId[id] = n; }
  return n;
}
function uniqueNodes(edges){
  const s = new Set(); edges.forEach(([a,b])=>{s.add(a);s.add(b);});
  return [...s];
}
function layout(sim){
  const groups = {};
  sim.nodes.forEach(n => {
    const top = pkgOf(n.id);
    (groups[top] = groups[top] || []).push(n);
  });
  const tops = Object.keys(groups);
  tops.forEach((t, ti) => {
    const members = groups[t];
    const base = (ti / tops.length) * 2 * Math.PI;
    members.forEach((n, mi) => {
      const a = base + (mi / members.length) * 1.7;
      const r = members.length > 1 ? 140 : 0;
      n.x = sim.w / 2 + Math.cos(a) * (r + (ti % 3) * 75);
      n.y = sim.h / 2 + Math.sin(a) * (r + (ti % 3) * 48);
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
        const d = Math.sqrt(d2), f = 2400 / d2;
        dx /= d; dy /= d;
        a.vx += dx * f; a.vy += dy * f;
        b.vx -= dx * f; b.vy -= dy * f;
      }
      a.vx += (w / 2 - a.x) * 0.0045;
      a.vy += (h / 2 - a.y) * 0.0045;
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
function chips(items, max=12){
  const shown = items.slice(0, max);
  return shown.length
    ? `<div class="chips">` + shown.map(q=>`<span data-q="${esc(q)}">${esc(q.split('.').slice(-2).join('.'))}</span>`).join('') +
      (items.length > max ? `<span>+${items.length-max}…</span>` : '') + `</div>`
    : '<div class="chips">—</div>';
}
function depsDetail(id){
  const outs = DATA.moduleDeps[id] || [];
  const ins = Object.entries(DATA.moduleDeps).filter(([, ts]) => ts.includes(id)).map(([m]) => m);
  return `<b>${esc(id)}</b> · 被依赖 ${ins.length} · 依赖 ${outs.length}`
    + `<div style="margin-top:4px">依赖 → ${outs.length ? chips(outs) : '—'}</div>`
    + `<div style="margin-top:4px">被依赖 ← ${ins.length ? chips(ins) : '—'}</div>`;
}
function callsDetail(id){
  const outs = DATA.callEdges.filter(([a]) => a === id).map(([, b]) => b);
  const ins = DATA.callEdges.filter(([, b]) => b === id).map(([a]) => a);
  return `<b>${esc(id)}</b> · 调用 ${outs.length} · 被调用 ${ins.length}`
    + `<div style="margin-top:4px">调用 → ${outs.length? chips(outs):'—'}</div>`
    + `<div style="margin-top:4px">被调用 ← ${ins.length? chips(ins):'—'}</div>`;
}

/* ---- charts: donuts + heatmap + health ---- */
const GRADE_COLOR = {good:'#3ecf8e', ok:'#6aa6ff', warn:'#f0b453', bad:'#f26d6d'};
function drawHealth(){
  const h = DATA.health;
  const color = GRADE_COLOR[h.grade_class] || '#6aa6ff';
  const R = 52, C = 2 * Math.PI * R, frac = h.total / 100;
  document.getElementById('healthdial').innerHTML =
    `<svg width="140" height="140">
      <circle r="${R}" cx="70" cy="70" fill="none" stroke="#1a2338" stroke-width="14"/>
      <circle r="${R}" cx="70" cy="70" fill="none" stroke="${color}" stroke-width="14"
        stroke-linecap="round" stroke-dasharray="${(frac*C).toFixed(1)} ${C}"
        transform="rotate(-90 70 70)"/>
      <text x="70" y="66" text-anchor="middle" fill="${color}" font-size="26" font-weight="800">${h.total}</text>
      <text x="70" y="86" text-anchor="middle" fill="#8d9bbd" font-size="11">${esc(h.grade)}</text>
    </svg>`;
  document.getElementById('healthbars').innerHTML = h.dimensions.map(d=>{
    const pct = d.max_penalty ? Math.round(d.penalty / d.max_penalty * 100) : 0;
    const pc = pct >= 60 ? 'var(--bad)' : pct >= 30 ? 'var(--warn)' : 'var(--good)';
    return `<div class="dimrow">
      <span class="dn">${esc(d.name)}</span>
      <span class="dm"><div class="meter"><div style="width:${pct}%;background:${pc}"></div></div></span>
      <span class="dv" title="${esc(d.detail)}">${esc(d.detail)}</span>
      <span class="dp" style="color:${d.penalty ? 'var(--warn)' : 'var(--good)'}">${d.penalty ? '-'+d.penalty : '满分'}</span>
    </div>`;
  }).join('');
}
function donut(el, entries, colors){
  const total = entries.reduce((s,[,v])=>s+v,0) || 1;
  const R = 52, C = 2 * Math.PI * R;
  let off = 0, segs = '';
  entries.forEach(([k, v], i)=>{
    const frac = v / total;
    segs += `<circle r="${R}" cx="70" cy="70" fill="none" stroke="${colors[i % colors.length]}"
      stroke-width="17" stroke-dasharray="${(frac*C-2).toFixed(1)} ${(C-frac*C+2).toFixed(1)}"
      stroke-dashoffset="${(-off).toFixed(1)}" transform="rotate(-90 70 70)"><title>${esc(k)}: ${v}</title></circle>`;
    off += frac * C;
  });
  el.innerHTML = `<svg width="140" height="140">${segs}
    <text x="70" y="66" text-anchor="middle" fill="#e8eefb" font-size="20" font-weight="700">${total}</text>
    <text x="70" y="84" text-anchor="middle" fill="#8d9bbd" font-size="10.5">总计</text></svg>`;
}
function drawCharts(){
  /* language donut */
  const byLang = {};
  DATA.files.forEach(f => byLang[f.language] = (byLang[f.language]||0) + f.code);
  const langs = Object.entries(byLang).sort((a,b)=>b[1]-a[1]);
  donut(document.getElementById('donut-lang'), langs, PALETTE);
  document.getElementById('leg-lang').innerHTML = langs.map(([k,v],i)=>
    `<div><i style="background:${PALETTE[i%PALETTE.length]}"></i>${esc(k)} <b>${v.toLocaleString()}</b></div>`).join('');
  /* symbol kind donut */
  const byKind = {};
  DATA.symbols.forEach(s => byKind[s.kind] = (byKind[s.kind]||0) + 1);
  const kinds = Object.entries(byKind).sort((a,b)=>b[1]-a[1]);
  donut(document.getElementById('donut-kind'), kinds, ['#6aa6ff','#a08cff','#4fd6d2','#f0b453','#e87bb0']);
  document.getElementById('leg-kind').innerHTML = kinds.map(([k,v],i)=>
    `<div><i style="background:${['#6aa6ff','#a08cff','#4fd6d2','#f0b453','#e87bb0'][i%5]}"></i>${esc(k)} <b>${v}</b></div>`).join('');
  /* heatmap: top 120 files by code lines */
  const heat = document.getElementById('heat');
  const info = document.getElementById('heatinfo');
  const files = DATA.files.slice(0, 120);
  const max = Math.max(1, ...files.map(f=>f.code));
  heat.innerHTML = files.map(f=>{
    const t = f.code / max;
    const bg = t > .75 ? '#6aa6ff' : t > .5 ? '#5481d8' : t > .3 ? '#3f5da8' : t > .15 ? '#31456f' : '#26314e';
    return `<div class="cell" style="background:${bg}" data-p="${esc(f.path)}" title="${esc(f.path)} · ${f.code} 行"></div>`;
  }).join('');
  heat.querySelectorAll('.cell').forEach(c=>{
    c.onmouseenter = () => info.textContent = c.dataset.p;
    c.onclick = () => { showTab('src'); openFile(c.dataset.p); };
  });
  drawHealth();
}

/* ---- source browser with syntax highlighting ---- */
const fileList = document.getElementById('filelist');
const srcWrap = document.getElementById('srcwrap');
const symBox = document.getElementById('symbox');
const symsByFile = {};
DATA.symbols.forEach(s => { (symsByFile[s.file] = symsByFile[s.file] || []).push(s); });
const KW = /\b(def|class|return|if|elif|else|for|while|try|except|finally|with|as|import|from|async|await|yield|lambda|pass|break|continue|raise|in|not|and|or|is|None|True|False|self|cls|global|assert|del|print)\b/g;
function hl(line){
  let s = esc(line);
  s = s.replace(/(#.*$)/, '<span class="tk-c">$1</span>');
  s = s.replace(/(&quot;.*?&quot;|'[^']*'|"[^"]*")/g, '<span class="tk-s">$1</span>');
  s = s.replace(/(@[\w.]+)/g, '<span class="tk-d">$1</span>');
  s = s.replace(/\b(\d+\.?\d*)\b/g, '<span class="tk-n">$1</span>');
  s = s.replace(KW, '<span class="tk-k">$1</span>');
  s = s.replace(/\b(def|class)\s+([A-Za-z_]\w*)/g, '$1 <span class="tk-f">$2</span>');
  return s;
}
function openFile(path, line){
  if (!(path in DATA.sources)){
    srcWrap.innerHTML = `<pre class="src"><span class="lc">⚠ 该文件未嵌入报告(仅嵌入代码行最多的 ${DATA.embeddedLimit} 个文件)。请用命令行或编辑器查看完整内容。</span></pre>`;
    symBox.innerHTML = '';
    [...fileList.children].forEach(c => c.classList.toggle('sel', c.dataset.path === path));
    return;
  }
  [...fileList.children].forEach(c => c.classList.toggle('sel', c.dataset.path === path));
  const lines = DATA.sources[path] || [];
  let body = '';
  lines.forEach((l, i) => {
    const on = (line && i + 1 === line) ? ' on' : '';
    body += `<span class="ln">${i + 1}</span><span class="lc${on}">${hl(l) || ' '}</span>\n`;
  });
  const cut = DATA.truncatedFiles[path];
  if (cut){
    body += `<span class="ln">…</span><span class="lc" style="color:#8d9bbd">`
          + `⚠ 该文件共 ${cut} 行,报告仅嵌入前 ${lines.length} 行</span>\n`;
  }
  srcWrap.innerHTML = `<pre class="src">${body}</pre>`;
  symBox.innerHTML = '';
  (symsByFile[path] || []).forEach(s => {
    const el = document.createElement('span');
    el.textContent = `${s.kind === 'async_function' ? 'async ' : ''}${s.kind === 'class' ? '◆ ' : 'ƒ '}${s.name}`;
    el.title = `L${s.line}${s.kind !== 'class' ? ' · 复杂度 ' + s.cx : ''}`;
    el.onclick = () => openFile(path, s.line);
    symBox.appendChild(el);
  });
  if (line){
    const target = srcWrap.querySelector('.lc.on');
    if (target) target.scrollIntoView({block: 'center'});
  } else srcWrap.scrollTop = 0;
}
DATA.files.filter(f => DATA.sources[f.path]).forEach(f => {
  const d = document.createElement('div');
  d.textContent = f.path;
  d.dataset.path = f.path;
  d.onclick = () => openFile(f.path);
  fileList.appendChild(d);
});
if (fileList.firstChild) openFile(fileList.firstChild.dataset.path);

/* ---- search: dim graph nodes + filter file list ---- */
document.getElementById('search').addEventListener('input', e => {
  const q = e.target.value.toLowerCase();
  document.querySelectorAll('.graph circle').forEach(c => {
    c.classList.toggle('dim', !!q && !c.dataset.id.toLowerCase().includes(q));
  });
  document.querySelectorAll('.graph path').forEach(p => {
    const hit = !q || (p.dataset.s && p.dataset.s.toLowerCase().includes(q))
             || (p.dataset.t && p.dataset.t.toLowerCase().includes(q));
    p.classList.toggle('dim', !!q && !hit);
  });
  document.querySelectorAll('#filelist div').forEach(d => {
    d.style.display = (!q || d.dataset.path.toLowerCase().includes(q)) ? '' : 'none';
  });
});
function jumpToSymbol(q){
  const s = DATA.symbols.find(x => x.q === q);
  if (s){ showTab('src'); openFile(s.file, s.line); }
}

/* header score chip */
(function(){
  const h = DATA.health;
  const color = GRADE_COLOR[h.grade_class] || '#6aa6ff';
  document.getElementById('scorenum').textContent = h.total;
  document.getElementById('scorenum').classList.add('g-' + h.grade_class);
  const R = 19, C = 2 * Math.PI * R, frac = h.total / 100;
  document.getElementById('scoredial').innerHTML =
    `<svg width="48" height="48">
      <circle r="${R}" cx="24" cy="24" fill="none" stroke="#1a2338" stroke-width="5"/>
      <circle r="${R}" cx="24" cy="24" fill="none" stroke="${color}" stroke-width="5"
        stroke-linecap="round" stroke-dasharray="${(frac*C).toFixed(1)} ${C}"
        transform="rotate(-90 24 24)"/>
    </svg>`;
})();

/* landing tab: make the conclusion useful before rendering heavier graphs */
window.addEventListener('load', () => drawOverview());
"""

_TABLE = ""  # reserved


def render_interactive_report(analyzer: RepoAnalyzer, path: str) -> str:
    data = _collect_data(analyzer)
    page = render_page(data, _CSS + _TABLE, _JS, esc)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return str(out)
