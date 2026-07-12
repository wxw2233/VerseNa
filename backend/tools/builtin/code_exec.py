import asyncio
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
        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-c", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
            output = stdout.decode() + stderr.decode()
            return output[:2000] or "(无输出)"
        except asyncio.TimeoutError:
            return "执行超时（15秒）"
        except Exception as e:
            return f"执行失败: {e}"

def register(registry):
    registry.register(CodeExecTool())
