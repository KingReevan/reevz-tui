import ast
import re
from typing import Union

_ALLOWED_CHARS_RE = re.compile(r"^[0-9\s\+\-\*\/\^\(\)\.]+$")


def looks_like_math(text: str) -> bool:
    stripped = text.lstrip()
    if not stripped:
        return False
    first = stripped[0]
    return first.isdigit() or first in "-("


def eval_math_expression(expression: str) -> Union[int, float]:
    cleaned = expression.strip()
    if not cleaned:
        raise ValueError("Empty expression.")
    if not _ALLOWED_CHARS_RE.match(cleaned):
        raise ValueError(
            "Only digits, +, -, *, /, ^, parentheses, and decimals are allowed."
        )

    normalized = cleaned.replace("^", "**")
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Invalid math expression.") from exc

    # Evaluate a safe subset of the AST without calling eval.
    result = _eval_node(tree.body)
    return result


def _eval_node(node: ast.AST) -> Union[int, float]:
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left**right
        raise ValueError("Unsupported operator.")

    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise ValueError("Unsupported unary operator.")

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("Only numbers are allowed.")
        return node.value

    raise ValueError("Invalid math expression.")
