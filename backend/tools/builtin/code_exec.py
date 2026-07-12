import asyncio
import shlex
from tools.base import BaseTool

class CodeExecTool(BaseTool):
    name = "code_exec"
    description = "执行 Python 代码并返回输出"
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "要执行的 Python 代码"}
        },
        "required": ["code"]
    }

    async def execute(self, code: str = "", **kwargs) -> str:
        if not code or not code.strip():
            return "错误：没有提供代码"

        # 清理代码：去掉可能的 markdown 代码块标记
        code = code.strip()
        if code.startswith("```python"):
            code = code[9:]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        code = code.strip()

        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-c", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
            output = stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")
            if proc.returncode != 0 and output.strip():
                return f"执行错误 (exit {proc.returncode}):\n{output[:2000]}"
            return output[:2000] or "(无输出)"
        except asyncio.TimeoutError:
            return "执行超时（15秒）"
        except FileNotFoundError:
            return "错误：找不到 python 命令，请确认 Python 已安装并在 PATH 中"
        except Exception as e:
            return f"执行失败: {type(e).__name__}: {e}"

def register(registry):
    registry.register(CodeExecTool())
