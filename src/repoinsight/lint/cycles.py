"""Circular dependency detection (Tarjan's strongly connected components)."""

from __future__ import annotations

from typing import Dict, List, Set

from dataclasses import dataclass, field


@dataclass
class Finding:
    """One lint result. kind: "circular_dependency" | "dead_symbol" |
    "unused_import" | "layer_violation". severity: "error" | "warning"."""

    kind: str
    severity: str
    message: str
    items: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {"kind": self.kind, "severity": self.severity,
                "message": self.message, "items": self.items}


def find_cycles(module_dependencies: Dict[str, List[str]]) -> List[List[str]]:
    """Return strongly connected components that form import cycles.

    Each returned cycle is a sorted list of module names. Components with a
    single module are only cycles if the module imports itself.
    """
    graph: Dict[str, List[str]] = {
        mod: list(deps) for mod, deps in module_dependencies.items()
    }
    for deps in list(graph.values()):
        for dep in deps:
            graph.setdefault(dep, [])

    index_counter = [0]
    stack: List[str] = []
    on_stack: Set[str] = set()
    index: Dict[str, int] = {}
    lowlink: Dict[str, int] = {}
    result: List[List[str]] = []

    # Iterative Tarjan to stay safe on deep graphs.
    for start in sorted(graph):
        if start in index:
            continue
        work = [(start, 0)]
        while work:
            node, dep_i = work[-1]
            if dep_i == 0:
                index[node] = lowlink[node] = index_counter[0]
                index_counter[0] += 1
                stack.append(node)
                on_stack.add(node)
            advanced = False
            deps = graph.get(node, [])
            while dep_i < len(deps):
                nxt = deps[dep_i]
                dep_i += 1
                if nxt not in index:
                    work[-1] = (node, dep_i)
                    work.append((nxt, 0))
                    advanced = True
                    break
                if nxt in on_stack:
                    lowlink[node] = min(lowlink[node], index[nxt])
            if advanced:
                continue
            work[-1] = (node, dep_i)
            work.pop()
            if lowlink[node] == index[node]:
                component: List[str] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                is_cycle = len(component) > 1 or node in graph.get(node, [])
                if is_cycle:
                    result.append(sorted(component))
            if work:
                parent = work[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[node])
    return sorted(result, key=lambda c: (len(c), c))
