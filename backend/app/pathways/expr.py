"""Tiny, safe expression evaluator for pathway rules written in config/pathways/*.json.

Rules are plain Python-like boolean expressions, e.g.
    "fever and platelets is not None and platelets < 20000"
    "age_years >= 40 and not chest_wall"
Only names, numbers/strings, and/or/not, comparisons and a few helper calls (known, no) are allowed; anything
else is rejected at load time. Unknown names evaluate to False (signs not mentioned), numeric slots may be None,
and a comparison involving None is False, so a missing slot can never make a rule fire.
"""
from __future__ import annotations

import ast
from functools import lru_cache
from typing import Any, Callable

_ALLOWED = (ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.Compare, ast.Name, ast.Load,
            ast.Constant, ast.Call, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq, ast.Is, ast.IsNot, ast.In,
            ast.Tuple, ast.List)
_FUNCS = {"known", "no", "named"}


class RuleError(ValueError):
    pass


@lru_cache(maxsize=4096)
def compile_expr(src: str) -> ast.Expression:
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError as e:
        raise RuleError(f"bad rule {src!r}: {e}") from e
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise RuleError(f"rule {src!r}: {type(node).__name__} not allowed")
        if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and node.func.id in _FUNCS):
            raise RuleError(f"rule {src!r}: only {sorted(_FUNCS)} calls are allowed")
    return tree


def names_in(src: str) -> set[str]:
    return {n.id for n in ast.walk(compile_expr(src)) if isinstance(n, ast.Name) and n.id not in _FUNCS}


def evaluate(src: str, facts: dict[str, Any], funcs: dict[str, Callable[..., Any]]) -> bool:
    return bool(_ev(compile_expr(src).body, facts, funcs))


def _ev(n: ast.AST, facts: dict, funcs: dict) -> Any:
    if isinstance(n, ast.BoolOp):
        if isinstance(n.op, ast.And):
            return all(_ev(v, facts, funcs) for v in n.values)
        return any(_ev(v, facts, funcs) for v in n.values)
    if isinstance(n, ast.UnaryOp):
        return not _ev(n.operand, facts, funcs)
    if isinstance(n, ast.Name):
        return facts.get(n.id, False)
    if isinstance(n, ast.Constant):
        return n.value
    if isinstance(n, (ast.Tuple, ast.List)):
        return [_ev(e, facts, funcs) for e in n.elts]
    if isinstance(n, ast.Call):
        args = [a.id if isinstance(a, ast.Name) else _ev(a, facts, funcs) for a in n.args]
        return funcs[n.func.id](*args)
    if isinstance(n, ast.Compare):
        left = _ev(n.left, facts, funcs)
        for op, comp in zip(n.ops, n.comparators):
            right = _ev(comp, facts, funcs)
            if isinstance(op, ast.Is):
                ok = left is right
            elif isinstance(op, ast.IsNot):
                ok = left is not right
            elif isinstance(op, ast.In):
                ok = left in (right or [])
            elif left is None or right is None or isinstance(left, bool) or isinstance(right, bool):
                ok = (op.__class__ is ast.Eq and left == right) or (op.__class__ is ast.NotEq and left != right)
            elif isinstance(op, ast.Lt):
                ok = left < right
            elif isinstance(op, ast.LtE):
                ok = left <= right
            elif isinstance(op, ast.Gt):
                ok = left > right
            elif isinstance(op, ast.GtE):
                ok = left >= right
            elif isinstance(op, ast.Eq):
                ok = left == right
            else:
                ok = left != right
            if not ok:
                return False
            left = right
        return True
    raise RuleError(f"unsupported node {type(n).__name__}")
