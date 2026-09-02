"""Load the bundled frontend assets used by the offline report."""

from __future__ import annotations

from importlib.resources import files


def load_assets() -> tuple[str, str]:
    assets = files("repoinsight.report.assets")
    css = assets.joinpath("styles.css").read_text(encoding="utf-8")
    javascript = assets.joinpath("report.js").read_text(encoding="utf-8")
    return css, javascript
