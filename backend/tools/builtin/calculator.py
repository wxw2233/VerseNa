import math
import ast
import operator
from tools.base import BaseTool

# 安全的运算符映射
SAFE_OPERATORS = {
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

# 安全的数学函数
SAFE_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "exp": math.exp,
    "ceil": math.ceil,
    "floor": math.floor,
    "pi": math.pi,
    "e": math.e,
    "factorial": math.factorial,
}


def _safe_eval(node):
    """安全地求值 AST 节点"""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    elif isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, complex)):
            return node.value
        raise ValueError(f"不支持的常量类型: {type(node.value)}")
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in SAFE_OPERATORS:
            raise ValueError(f"不支持的运算符: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return SAFE_OPERATORS[op_type](left, right)
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in SAFE_OPERATORS:
            raise ValueError(f"不支持的运算符: {op_type.__name__}")
        return SAFE_OPERATORS[op_type](_safe_eval(node.operand))
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in SAFE_FUNCTIONS:
            func = SAFE_FUNCTIONS[node.func.id]
            if callable(func):
                args = [_safe_eval(arg) for arg in node.args]
                return func(*args)
        raise ValueError(f"不支持的函数调用")
    elif isinstance(node, ast.Name):
        if node.id in SAFE_FUNCTIONS:
            val = SAFE_FUNCTIONS[node.id]
            if not callable(val):
                return val
        raise ValueError(f"未知变量: {node.id}")
    else:
        raise ValueError(f"不支持的表达式类型: {type(node).__name__}")


class CalculatorTool(BaseTool):
    name = "calculator"
    description = "数学计算器，支持基本运算、幂运算、三角函数等。示例：2+3*4, sqrt(16), sin(pi/2)"
    parameters = {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "数学表达式，如 '2+3*4' 或 'sqrt(16)'"}
        },
        "required": ["expression"]
    }

    async def execute(self, expression: str = "", **kwargs) -> str:
        if not expression or not expression.strip():
            return "错误：请提供数学表达式"

        expr = expression.strip()

        try:
            tree = ast.parse(expr, mode='eval')
            result = _safe_eval(tree)

            # 格式化结果
            if isinstance(result, float):
                if result == int(result) and abs(result) < 1e15:
                    return f"{expr} = {int(result)}"
                return f"{expr} = {result:.10g}"
            return f"{expr} = {result}"

        except ZeroDivisionError:
            return f"错误：除以零 — {expr}"
        except ValueError as e:
            return f"计算错误：{e}"
        except SyntaxError:
            return f"语法错误，请检查表达式：{expr}"
        except Exception as e:
            return f"计算失败：{type(e).__name__}: {e}"


def register(registry):
    registry.register(CalculatorTool())
