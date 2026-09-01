"""Command-line interface for repoinsight."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .analyzer import RepoAnalyzer
from .output import (
    write_call_dot,
    write_json,
    write_module_dot,
    write_summary_text,
)
from .report import render_html_report
from .report.interactive import render_interactive_report


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="repoinsight",
        description="Python 代码库静态分析工具:符号表、调用图、模块依赖图与代码度量。",
    )
    p.add_argument("--version", action="version", version=f"repoinsight {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("path", help="要分析的项目根目录")
        sp.add_argument("-o", "--output", help="输出文件(默认打印到屏幕或自动命名)")
        sp.add_argument("--ignore", nargs="*", default=[], help="额外要跳过的目录名")

    sp_scan = sub.add_parser("summary", help="打印项目文字摘要")
    common(sp_scan)

    sp_json = sub.add_parser("json", help="完整分析结果导出为 JSON")
    common(sp_json)

    sp_dep = sub.add_parser("modules", help="模块依赖图(Graphviz DOT 格式)")
    common(sp_dep)

    sp_call = sub.add_parser("calls", help="函数调用图(Graphviz DOT 格式)")
    common(sp_call)
    sp_call.add_argument("--max-nodes", type=int, default=120,
                         help="只画最活跃的 N 个函数(默认 120)")

    sp_report = sub.add_parser("report", help="生成 HTML 报告(浏览器直接打开)")
    common(sp_report)
    sp_report.add_argument("--interactive", action="store_true",
                           help="交互式报告:力导向图、源码浏览器、搜索")
    sp_report.add_argument("--open", action="store_true",
                           help="生成后自动用默认浏览器打开")

    sp_who = sub.add_parser("who-calls", help="查一个函数被谁调用、它调用谁")
    common(sp_who)
    sp_who.add_argument("symbol", help="函数名(短名或完整限定名)")

    sp_lint = sub.add_parser("lint", help="检查循环依赖、死代码、分层规则")
    common(sp_lint)
    sp_lint.add_argument("--rules", help="分层规则 JSON 文件"
                                          '{"forbidden_edges": [[调用方, 被调用方], ...]}')

    sp_hot = sub.add_parser("hotspots", help="按「改动频率 × 代码量」排热点文件(需要 git)")
    common(sp_hot)
    sp_hot.add_argument("--top", type=int, default=20, help="显示前几个文件(默认 20)")

    return p


_KIND_LABELS = {
    "circular_dependency": "循环依赖",
    "dead_symbol": "疑似死代码",
    "unused_import": "未使用的导入",
    "layer_violation": "违反分层规则",
}
_SEVERITY_LABELS = {"error": "错误", "warning": "警告"}


def _cmd_summary(analyzer: RepoAnalyzer, args: argparse.Namespace) -> int:
    if args.output:
        write_summary_text(analyzer, args.output)
        print(f"摘要已写入 {args.output}")
    else:
        sys.stdout.write(write_summary_text(analyzer))
    return 0


def _cmd_json(analyzer: RepoAnalyzer, args: argparse.Namespace) -> int:
    out = args.output or "repoinsight.json"
    write_json(analyzer, out)
    print(f"JSON 已写入 {out}")
    return 0


def _cmd_modules(analyzer: RepoAnalyzer, args: argparse.Namespace) -> int:
    out = args.output or "modules.dot"
    write_module_dot(analyzer, out)
    print(f"DOT 图已写入 {out}")
    return 0


def _cmd_calls(analyzer: RepoAnalyzer, args: argparse.Namespace) -> int:
    out = args.output or "calls.dot"
    write_call_dot(analyzer, out, max_nodes=args.max_nodes)
    print(f"DOT 图已写入 {out}")
    return 0


def _cmd_report(analyzer: RepoAnalyzer, args: argparse.Namespace) -> int:
    out = args.output or "repoinsight-report.html"
    if args.interactive:
        render_interactive_report(analyzer, out)
    else:
        render_html_report(analyzer, out)
    print(f"HTML 报告已写入 {out}(用浏览器打开即可)")
    if args.open:
        import webbrowser
        webbrowser.open(f"file://{Path(out).resolve()}")
    return 0


def _cmd_lint(analyzer: RepoAnalyzer, args: argparse.Namespace) -> int:
    from .lint import run_all
    rules = None
    if args.rules and Path(args.rules).exists():
        import json as _json
        rules = _json.loads(Path(args.rules).read_text(encoding="utf-8"))
    findings = run_all(analyzer.result, rules=rules)
    if not findings:
        print("没有发现任何问题,很干净")
        return 0
    for f in findings:
        kind = _KIND_LABELS.get(f.kind, f.kind)
        severity = _SEVERITY_LABELS.get(f.severity, f.severity)
        print(f"[{severity}] {kind}:{f.message}")
    if args.output:
        import json as _json
        Path(args.output).write_text(
            _json.dumps([f.to_dict() for f in findings], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"检查结果已写入 {args.output}")
    return 1 if any(f.severity == "error" for f in findings) else 0


def _cmd_hotspots(analyzer: RepoAnalyzer, args: argparse.Namespace) -> int:
    from .gitinfo import combine_hotspots, git_hotspots
    spots = git_hotspots(analyzer.root)
    rows = combine_hotspots(analyzer.file_metrics(), spots)
    for r in rows[: args.top]:
        print(f"  热度 {r['score']:.3f}  提交 {r['commits']:<4} 次  {r['path']}")
    if args.output:
        import json as _json
        Path(args.output).write_text(
            _json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"热点数据已写入 {args.output}")
    return 0


def _cmd_who_calls(analyzer: RepoAnalyzer, args: argparse.Namespace) -> int:
    target = args.symbol
    matches = [s for s in analyzer.result.symbols
               if s.is_function_like and (s.qualified_name == target
                                          or s.qualified_name.endswith("." + target)
                                          or s.name == target)]
    if not matches:
        print(f"找不到匹配 {target!r} 的函数")
        return 1
    for m in matches:
        print(f"{m.qualified_name}  ({m.file}:{m.line_start})")
        callers = analyzer.callers_of(m.qualified_name)
        callees = analyzer.callees_of(m.qualified_name)
        print(f"  被谁调用({len(callers)} 处):")
        for c in callers:
            print(f"    <- {c}")
        if not callers:
            print("    (项目内没有调用者)")
        print(f"  调用了({len(callees)} 处):")
        for c in callees:
            print(f"    -> {c}")
        if not callees:
            print("    (没有调用项目内的函数)")
    return 0


_COMMANDS = {
    "summary": _cmd_summary,
    "json": _cmd_json,
    "modules": _cmd_modules,
    "calls": _cmd_calls,
    "report": _cmd_report,
    "lint": _cmd_lint,
    "hotspots": _cmd_hotspots,
    "who-calls": _cmd_who_calls,
}


def _run(args: argparse.Namespace) -> int:
    root = Path(args.path)
    if not root.exists():
        print(f"错误:路径不存在:{root}", file=sys.stderr)
        return 2
    analyzer = RepoAnalyzer(str(root), ignored_dirs=args.ignore)
    analyzer.analyze()
    return _COMMANDS[args.command](analyzer, args)


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        return _run(args)
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
