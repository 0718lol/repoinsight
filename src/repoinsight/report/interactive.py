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
from .interactive_assets import load_assets
from .interactive_template import render_page


def esc(v) -> str:
    return _html.escape(str(v), quote=False)


# ---------------------------------------------------------------------- #
_collect_data = collect_data


def render_interactive_report(analyzer: RepoAnalyzer, path: str) -> str:
    data = _collect_data(analyzer)
    css, javascript = load_assets()
    page = render_page(data, css, javascript, esc)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return str(out)
