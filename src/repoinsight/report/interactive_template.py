"""HTML shell for the interactive report.

The template receives prepared data and frontend assets as inputs. Keeping
this boundary separate makes layout changes independent from analysis logic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict


def render_page(data: Dict, css: str, javascript: str, esc: Callable) -> str:
    """Render and write the self-contained interactive report."""
    summary = data["summary"]

    def card(number: int, label: str, color: str = "") -> str:
        return (f"<div class='card' style='--ac:{color}'>"
                f"<div class='num' data-v='{number}'>0</div>"
                f"<div class='lbl'>{label}</div></div>")

    cards = "".join([
        card(summary["files"], "文件总数", "#6aa6ff"),
        card(summary["python_files"], "Python 文件", "#a08cff"),
        card(summary["code_lines"], "代码行", "#4fd6d2"),
        card(summary["functions"], "函数 / 方法", "#3ecf8e"),
        card(summary["module_dependencies"], "模块依赖边", "#f0b453"),
        card(summary["call_edges"], "调用关系", "#e87bb0"),
        card(summary["parse_errors"], "解析错误",
             "#f26d6d" if summary["parse_errors"] else "#3ecf8e"),
    ])

    max_complexity = max((row["complexity"] for row in data["complexity"]), default=1)
    complexity_rows = ""
    for row in data["complexity"]:
        complexity = row["complexity"]
        badge = "b-critical" if complexity >= 15 else ("b-high" if complexity >= 8 else "b-ok")
        percent = int(complexity / max_complexity * 100)
        qualified_name = esc(row["name"])
        complexity_rows += (
            f"<tr><td class='num'><span class='badge {badge}'>{complexity}</span></td>"
            f"<td class='mono'><a href='#' onclick=\"jumpToSymbol('{qualified_name}');return false\" "
            f"style='color:inherit;text-decoration:none'>{qualified_name}</a></td>"
            f"<td class='mono'>{esc(row['file'])}:{row['line']}</td>"
            f"<td><div class='meter'><div style='width:{percent}%'></div></div></td></tr>"
        )

    coupling_rows = ""
    ranked = sorted(
        data["coupling"].items(), key=lambda item: -(item[1]["fan_in"] + item[1]["fan_out"])
    )[:40]
    for module, coupling in ranked:
        coupling_rows += (
            f"<tr><td class='mono'>{esc(module)}</td>"
            f"<td class='num'>{coupling['fan_in']}</td>"
            f"<td class='num'>{coupling['fan_out']}</td></tr>"
        )

    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>repoinsight · 代码库驾驶舱</title>
<style>{css}</style>
</head><body>
<header><div class="brand">
  <h1>⌘ repoinsight 驾驶舱</h1><span class="tag">交互式代码分析</span>
  <div id="scorechip" title="架构健康分:点「图谱总览」看扣分明细">
    <span id="scoredial"></span><span><span class="sc" id="scorenum">--</span><br><span class="sc-lbl">架构健康分</span></span>
  </div>
  <input id="search" placeholder="搜索 / 过滤 模块与文件…" autocomplete="off">
  <span class="root">{esc(summary['root'])}</span>
</div></header>
<main><div class="cards">{cards}</div>
  <div id="tabs" role="tablist" aria-label="报告视图">
    <button class="active" role="tab" aria-selected="true" data-tab="overview">① 先看结论</button>
    <button role="tab" aria-selected="false" data-tab="deps">② 模块依赖图</button>
    <button role="tab" aria-selected="false" data-tab="calls">③ 调用图</button>
    <button role="tab" aria-selected="false" data-tab="charts">④ 图谱总览</button>
    <button role="tab" aria-selected="false" data-tab="src">⑤ 源码浏览</button>
    <button role="tab" aria-selected="false" data-tab="cx">⑥ 复杂度</button>
    <button role="tab" aria-selected="false" data-tab="coupling">⑦ 耦合度</button>
  </div>

  <div class="tabpage active" id="tab-overview" role="tabpanel" aria-hidden="false">
    <h2>项目结论 <span class="hint">先判断风险，再进入对应明细</span></h2>
    <div class="overview"><div class="overview-score" id="overview-score"></div>
      <div class="overview-panel"><h3>当前扫描范围</h3>
        <p>共 {summary['files']} 个文件，{summary['python_files']} 个 Python 文件，{summary['code_lines']:,} 行代码，识别到 {summary['functions']} 个函数 / 方法。</p>
        <div class="overview-actions"><button data-jump="deps">查看模块依赖</button><button data-jump="cx">定位复杂度热点</button><button data-jump="src">浏览源码</button></div>
      </div>
    </div>
    <div class="overview-panel" style="margin-top:14px"><h3>需要关注</h3><div class="signals" id="overview-signals"></div></div>
  </div>
  <div class="tabpage" id="tab-deps" role="tabpanel" aria-hidden="true"><h2>模块依赖图 <span class="hint">拖动节点 · 滚轮缩放 · 悬停看连线 · 点击看详情 · 键盘 1-7 切页</span><label style="margin-left:auto;font-weight:400;text-transform:none;letter-spacing:0"><input type="checkbox" id="show-labels"> 显示全部标签</label></h2><div class="graph"><svg id="svg-deps"></svg></div><div class="detail" id="detail-deps">悬停高亮依赖连线（流动动画），点击节点查看详情。节点颜色 = 顶层包。</div><div class="legend" id="legend-deps"></div></div>
  <div class="tabpage" id="tab-calls" role="tabpanel" aria-hidden="true"><h2>调用图 <span class="hint">展示最活跃的 {len(data['callEdges'])} 条调用关系</span></h2><div class="graph"><svg id="svg-calls"></svg></div><div class="detail" id="detail-calls">点击函数节点，查看它调用谁 / 谁调用它。点击芯片名可跳转源码。</div></div>
  <div class="tabpage" id="tab-charts" role="tabpanel" aria-hidden="true"><h2>图谱总览</h2><div class="charts"><div class="chartbox"><h3>语言分布（按代码行）</h3><div class="donutwrap"><div id="donut-lang"></div><div class="dlegend" id="leg-lang"></div></div></div><div class="chartbox"><h3>符号类型分布</h3><div class="donutwrap"><div id="donut-kind"></div><div class="dlegend" id="leg-kind"></div></div></div><div class="chartbox" style="grid-column:1/-1"><h3>架构健康分（100 分制，扣分项一目了然）</h3><div class="donutwrap"><div id="healthdial"></div><div style="flex:1;min-width:320px" id="healthbars"></div></div></div><div class="chartbox" style="grid-column:1/-1"><h3>文件热力格（每格一个文件，越亮代码越多，悬停看路径，点击打开源码）</h3><div class="heat" id="heat"></div><div class="heatwrap" id="heatinfo">&nbsp;</div></div></div></div>
  <div class="tabpage" id="tab-src" role="tabpanel" aria-hidden="true"><h2>源码浏览器 <span class="hint">左侧选文件 · 底部符号芯片可跳转行</span></h2><div class="browser"><div id="filelist"></div><div><div id="srcwrap"></div><div id="symbox"></div></div></div></div>
  <div class="tabpage" id="tab-cx" role="tabpanel" aria-hidden="true"><h2>圈复杂度 前 40 名 <span class="hint">≥15 红 / 8–14 橙 / &lt;8 绿 · 点函数名跳源码</span></h2><table><tr><th class="num">复杂度</th><th>函数</th><th>位置</th><th style="width:24%"></th></tr>{complexity_rows}</table></div>
  <div class="tabpage" id="tab-coupling" role="tabpanel" aria-hidden="true"><h2>模块耦合度 <span class="hint">被依赖 = 有多少人引用它 · 依赖 = 它引用了多少人</span></h2><table><tr><th>模块</th><th class="num">被依赖数</th><th class="num">依赖数</th></tr>{coupling_rows}</table></div>
</main><footer>repoinsight · 纯静态分析 · 此文件完全离线可用</footer>
<script id="ri-data" type="application/json">{data_json}</script><script>{javascript}</script>
</body></html>"""
    return page
