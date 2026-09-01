# repoinsight 架构说明

> 目标:任何开发者(或 AI 模型)读完这一页,就知道代码怎么流转、改哪个需求动哪些文件。

## 一句话概括

扫描一个代码仓库 → 解析出「符号 / 导入 / 调用」 → 构建两张图(模块依赖图、函数调用图) → 用 CLI 或 HTML 报告输出。

## 数据流水线(逻辑链路)

```
 你敲命令                第 1 步              第 2 步                第 3 步                第 4 步
┌──────────┐      ┌──────────────┐    ┌───────────────┐    ┌────────────────┐    ┌──────────────┐
│ cli.py   │─────▶│ scanner.py   │───▶│ parsers/      │───▶│ module_graph.py│───▶│ output.py    │
│ (入口/分发)│      │ 找文件、数行数 │    │ python_parser │    │ call_graph.py  │    │ report/      │
└──────────┘      └──────────────┘    │ AST 提取符号   │    │ 建图 + 解析调用 │    │ (各种输出格式)│
                       │              │ /导入/调用     │    └────────────────┘    └──────────────┘
                       ▼              └───────┬───────┘            │
                 models.py                    ▼                    ▼
              (所有数据结构)          Symbol / Import 列表     AnalysisResult(汇总一切)
                                              │
                                ┌─────────────┼──────────────┐
                                ▼             ▼              ▼
                          lint/ 包       gitinfo.py     analyzer.py(编排者)
                        (体检:环/死码)  (git 热点)     (把上面全部串起来)
```

读代码就按这条链读:`cli → analyzer → scanner → parsers → module_graph / call_graph → output / report`。

## 分层规则(谁能引用谁)

```
┌─────────────────────────────────────────────┐
│ 入口层: cli.py                               │  只准调 编排层
├─────────────────────────────────────────────┤
│ 编排层: analyzer.py                          │  只准调 分析层 + 模型层
├─────────────────────────────────────────────┤
│ 分析层: scanner / parsers / module_graph /   │  只准调 模型层
│         call_graph / lint / gitinfo          │
├─────────────────────────────────────────────┤
│ 输出层: output.py / report/(html, interactive)│ 只准调 编排层(analyzer)读结果
├─────────────────────────────────────────────┤
│ 模型层: models.py(零依赖,被所有人引用)        │  不依赖任何人
└─────────────────────────────────────────────┘
```

依赖方向必须单向向下,不允许输出层反向调用分析层内部。

## 每个文件是干嘛的

| 文件 | 职责 | 关键入口 |
|---|---|---|
| `models.py` | 全部数据结构(SourceFile / Symbol / Import / AnalysisResult) | 只放数据,不放逻辑 |
| `scanner.py` | 走目录、识别语言、数代码行、跳过垃圾目录 | `RepoScanner.scan()` |
| `parsers/python_parser.py` | 用 AST 抽出类/函数/导入/调用/复杂度 | `PythonParser.parse()` |
| `module_graph.py` | 文件路径 ↔ 模块名换算;把 import 解析成本地模块;模块依赖边 | `ModuleGraph` |
| `call_graph.py` | 把「函数里调用了 X」解析成「具体哪个函数」 | `CallGraph.build()` |
| `analyzer.py` | **总编排**:调上面所有东西,产出 `AnalysisResult` 和各种报表数据 | `RepoAnalyzer.analyze()` |
| `lint/` | 体检:循环依赖(Tarjan)、死代码、分层规则 | `lint.run_all(result)` |
| `health.py` | 架构健康分:0-100 分 + 5 个维度的扣分明细 | `health.score(result)` |
| `compare.py` | 对比两个 git 版本:文件/符号/调用边/复杂度增减 | `compare_refs(root, a, b)` |
| `gitinfo.py` | git 历史:文件改动频率、两次提交 diff | `git_hotspots()` |
| `output.py` | 文字摘要 / JSON / DOT 图 | `write_*()` |
| `report/html_report.py` | 简版静态 HTML 报告 | `render_html_report()` |
| `report/interactive.py` | 交互式驾驶舱报告(力导向图/源码浏览/搜索) | `render_interactive_report()` |
| `cli.py` | 命令行入口;每条命令一个小函数 `_cmd_*` | `main()` |

## 贯穿全局的两个约定(改代码前必看)

1. **限定名规则**:每个函数在全项目有一个唯一名,格式 `包.模块.类.方法`,
   如 `repoinsight.analyzer.RepoAnalyzer.analyze`。
   解析器先产出文件内名字,由 `analyzer.analyze()` 统一加模块前缀(见 `module_graph.file_to_module`)。
   所有图、查询、lint 都靠这个名字对齐,**不要发明第二种拼法**。
2. **单一数据出口**:所有分析结果都装进 `AnalysisResult`(`models.py`)。
   下游(report / lint / CLI)只读它,不自己重新解析代码。

## 常见修改路径(照着做就行)

**① 加一门新语言的解析器(比如 Go)**
1. 新建 `src/repoinsight/parsers/go_parser.py`,接口照抄 `python_parser.py`:
   输入源码字符串,输出 `(List[Symbol], List[Import])`,限定名用「文件内相对名」。
2. 在 `scanner.py` 确认该后缀在 `LANGUAGE_BY_SUFFIX` 里。
3. 在 `analyzer.analyze()` 里加一个分支:`elif f.language == "go": ...`。
4. 新建 `tests/test_go_parser.py`,照抄 `test_python_parser.py` 的套路。

**② 加一个新度量(比如「最大嵌套深度」)**
1. 在解析阶段把它算出来,挂到 `models.Symbol` 上(加一个字段,默认值兜底)。
2. 在 `analyzer.py` 加一个 `xxx_report()` 方法返回排序好的列表。
3. CLI 想展示 → `cli.py` 加 `_cmd_xxx` 并注册进 `_COMMANDS`;
   报告想展示 → `report/interactive.py` 加一个标签页。

**③ 加一条 lint 规则**
1. 在 `lint/` 里新建文件,函数签名统一:`xxx(result) -> List[Finding]`(`Finding` 在 `lint/cycles.py`)。
2. 在 `lint/__init__.py` 的 `run_all()` 里追加调用。
3. 在 `cli.py` 的 `_KIND_LABELS` 里加中文标签。
4. 测试加到 `tests/test_lint.py`。
   (健康分会自动跟着变,因为 `health.score` 内部就是调 `run_all`。)

**③b 调整健康分算法**
1. 打开 `health.py` 的 `score()`:每个维度是一个 `Dimension(名称, 扣分, 上限, 说明)`。
2. 改权重或加维度都在那一个函数里;报告和 CLI 会自动展示新维度。

**④ 给交互报告加一个模块/图表**
1. 数据:在 `report/interactive.py` 的 `_collect_data()` 里加字段(纯 Python,先测 JSON)。
2. 展示:HTML 里加 `<div class="tabpage" id="tab-xxx">`,`_JS` 里加渲染函数。
3. 铁律:输出文件必须保持「零外部资源」——不引 CDN、不发网络请求。

**⑤ 加一条 CLI 命令**
1. `cli.py` 的 `build_arg_parser()` 里加 subparser(用 `common()` 补通用参数)。
2. 写 `_cmd_xxx(analyzer, args) -> int`,注册进 `_COMMANDS` 字典。`_run` 不用改。
3. 用户可见的所有字符串一律中文。

## 测试约定

- 测试在 `tests/`,运行:`python3 -m pytest tests/ -q`(无需安装,`conftest.py` 会把 `src` 加进路径)。
- `tests/conftest.py` 提供现成的 `sample_repo` 假项目和 `analysis` 分析结果,直接当 fixture 用。
- 每个新功能必须带测试;跑全量测试全绿才算完成。

## 目录总览

```
repoinsight/
├── src/repoinsight/          # 源码(分层见上)
│   ├── parsers/ report/ lint/   # 子包
├── tests/                    # pytest 测试
├── examples/sample_repo/     # 演示用小项目
├── .github/workflows/        # CI
├── ARCHITECTURE.md           # 本文件
└── README.md
```
