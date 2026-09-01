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
        description="Static analysis for Python codebases: symbols, call graphs, "
                    "module dependencies and code metrics.",
    )
    p.add_argument("--version", action="version", version=f"repoinsight {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("path", help="repository root to analyze")
        sp.add_argument("-o", "--output", help="output file (default: stdout or auto)")
        sp.add_argument("--ignore", nargs="*", default=[], help="extra directory names to skip")

    sp_scan = sub.add_parser("summary", help="print a text summary of the repo")
    common(sp_scan)

    sp_json = sub.add_parser("json", help="dump full analysis as JSON")
    common(sp_json)

    sp_dep = sub.add_parser("modules", help="module dependency graph (Graphviz DOT)")
    common(sp_dep)

    sp_call = sub.add_parser("calls", help="call graph (Graphviz DOT)")
    common(sp_call)
    sp_call.add_argument("--max-nodes", type=int, default=120,
                         help="limit graph to the busiest functions")

    sp_report = sub.add_parser("report", help="self-contained HTML report (open in a browser)")
    common(sp_report)
    sp_report.add_argument("--interactive", action="store_true",
                           help="interactive report: force graphs, source browser, search")
    sp_report.add_argument("--open", action="store_true",
                           help="open the report in the default browser afterwards")

    sp_who = sub.add_parser("who-calls", help="list callers/callees of a function")
    common(sp_who)
    sp_who.add_argument("symbol", help="function name (simple or qualified)")

    sp_lint = sub.add_parser("lint", help="circular deps, dead code, layer rules")
    common(sp_lint)
    sp_lint.add_argument("--rules", help="JSON file with layer rules "
                                          '{"forbidden_edges": [[importer, imported], ...]}')

    sp_hot = sub.add_parser("hotspots", help="files ranked by churn x size (needs git)")
    common(sp_hot)
    sp_hot.add_argument("--top", type=int, default=20, help="how many files to show")

    return p


def _run(args: argparse.Namespace) -> int:
    root = Path(args.path)
    if not root.exists():
        print(f"error: path does not exist: {root}", file=sys.stderr)
        return 2

    analyzer = RepoAnalyzer(str(root), ignored_dirs=args.ignore)
    analyzer.analyze()

    cmd = args.command
    if cmd == "summary":
        if args.output:
            write_summary_text(analyzer, args.output)
            print(f"summary written to {args.output}")
        else:
            sys.stdout.write(write_summary_text(analyzer))
        return 0

    if cmd == "json":
        out = args.output or "repoinsight.json"
        write_json(analyzer, out)
        print(f"JSON written to {out}")
        return 0

    if cmd == "modules":
        out = args.output or "modules.dot"
        write_module_dot(analyzer, out)
        print(f"DOT written to {out}")
        return 0

    if cmd == "calls":
        out = args.output or "calls.dot"
        write_call_dot(analyzer, out, max_nodes=args.max_nodes)
        print(f"DOT written to {out}")
        return 0

    if cmd == "report":
        out = args.output or "repoinsight-report.html"
        if args.interactive:
            render_interactive_report(analyzer, out)
        else:
            render_html_report(analyzer, out)
        print(f"HTML report written to {out}  (open it in a browser)")
        if args.open:
            import webbrowser
            webbrowser.open(f"file://{Path(out).resolve()}")
        return 0

    if cmd == "lint":
        from .lint import run_all
        rules = None
        if args.rules and Path(args.rules).exists():
            import json as _json
            rules = _json.loads(Path(args.rules).read_text(encoding="utf-8"))
        findings = run_all(analyzer.result, rules=rules)
        if not findings:
            print("no findings — clean")
            return 0
        for f in findings:
            print(f"[{f.severity}] {f.kind}: {f.message}")
        if args.output:
            import json as _json
            Path(args.output).write_text(
                _json.dumps([f.to_dict() for f in findings], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"findings written to {args.output}")
        return 1 if any(f.severity == "error" for f in findings) else 0

    if cmd == "hotspots":
        from .gitinfo import combine_hotspots, git_hotspots
        spots = git_hotspots(str(root))
        rows = combine_hotspots(analyzer.file_metrics(), spots)
        shown = 0
        for r in rows:
            if shown >= args.top:
                break
            print(f"  {r['score']:.3f}  commits={r['commits']:<4} {r['path']}")
            shown += 1
        if args.output:
            import json as _json
            Path(args.output).write_text(
                _json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"hotspot data written to {args.output}")
        return 0

    if cmd == "who-calls":
        matches = [s for s in analyzer.result.symbols
                   if s.is_function_like and (s.qualified_name == args.symbol
                                              or s.qualified_name.endswith("." + args.symbol)
                                              or s.name == args.symbol)]
        if not matches:
            print(f"no function matching {args.symbol!r}")
            return 1
        for m in matches:
            print(f"{m.qualified_name}  ({m.file}:{m.line_start})")
            callers = analyzer.callers_of(m.qualified_name)
            callees = analyzer.callees_of(m.qualified_name)
            print(f"  called by ({len(callers)}):")
            for c in callers:
                print(f"    <- {c}")
            if not callers:
                print("    (no internal callers)")
            print(f"  calls ({len(callees)}):")
            for c in callees:
                print(f"    -> {c}")
            if not callees:
                print("    (no internal callees)")
        return 0

    return 1


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        return _run(args)
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
