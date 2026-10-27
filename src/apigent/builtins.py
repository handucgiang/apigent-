"""Tools every agent gets by default."""

from __future__ import annotations

import ast
import operator
from typing import Any

from apigent.tools import Tool, ToolError, tool

_OPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
_FUNCS: dict[str, Any] = {"round": round, "abs": abs, "min": min, "max": max, "sum": sum}


def safe_eval(expr: str) -> float | int:
    """Evaluate an arithmetic expression without ``eval``."""

    def ev(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            if isinstance(node.op, ast.Pow) and abs(ev(node.right)) > 100:
                raise ToolError("exponent too large")
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        if isinstance(node, (ast.List, ast.Tuple)):
            return [ev(e) for e in node.elts]
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _FUNCS
            and not node.keywords
        ):
            return _FUNCS[node.func.id](*[ev(a) for a in node.args])
        raise ToolError(f"unsupported expression element: {type(node).__name__}")

    if len(expr) > 500:
        raise ToolError("expression too long")
    try:
        result = ev(ast.parse(expr, mode="eval"))
    except ZeroDivisionError as e:
        raise ToolError("division by zero") from e
    except SyntaxError as e:
        raise ToolError(f"invalid expression: {e.msg}") from e
    if not isinstance(result, (int, float)):
        raise ToolError("expression must produce a single number")
    return result


@tool
async def calculate(expression: str) -> dict[str, Any]:
    """Evaluate an arithmetic expression exactly. ALWAYS use this instead of doing math yourself
    (sums, differences, percentages, averages). Supports + - * / // % ** and
    round(), abs(), min(), max(), sum([...]). Example: "round(12 / 150 * 100, 2)"."""
    return {"expression": expression, "result": safe_eval(expression)}


def default_tools() -> list[Tool]:
    return [calculate]
