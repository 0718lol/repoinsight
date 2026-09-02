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
