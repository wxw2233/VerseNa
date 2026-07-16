import asyncio
import subprocess
from tools.base import BaseTool

class CodeExecTool(BaseTool):
    name = "code_exec"
    description = "执行 Python 代码或 shell 命令并返回输出"
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "要执行的 Python 代码或 shell 命令"}
        },
        "required": ["code"]
    }

    async def execute(self, code: str = "", base64_content: str = "", save_to: str = "", **kwargs) -> str:
        import base64 as b64

        # base64 写入大文件模式
        if base64_content and save_to:
            try:
                data = b64.b64decode(base64_content)
                import os
                os.makedirs(os.path.dirname(save_to) or '.', exist_ok=True)
                with open(save_to, 'wb') as f:
                    f.write(data)
                return f"成功写入 {len(data)} 字节到 {save_to}"
            except Exception as e:
                return f"写入失败: {e}"

        if not code or not code.strip():
            return "错误：没有提供代码"

        # 清理 markdown 代码块标记
        code = code.strip()
        if code.startswith("```python"):
            code = code[9:]
        elif code.startswith("```bash"):
            code = code[7:]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        code = code.strip()

        # 检测是否是 shell 命令（非 Python 语法）
        is_shell = any(code.startswith(cmd) for cmd in [
            'git ', 'pip ', 'npm ', 'cd ', 'mkdir ', 'rm ', 'cp ', 'mv ',
            'ls ', 'dir ', 'cat ', 'echo ', 'curl ', 'wget ', 'apt ',
            'sudo ', 'docker ', 'python ', 'node ',
        ])

        try:
            loop = asyncio.get_event_loop()
            if is_shell:
                result = await loop.run_in_executor(
                    None,
                    lambda: subprocess.run(
                        code, shell=True,
                        capture_output=True, text=True, timeout=120,
                        encoding="utf-8", errors="replace"
                    )
                )
            else:
                result = await loop.run_in_executor(
                    None,
                    lambda: subprocess.run(
                        ["python", "-c", code],
                        capture_output=True, text=True, timeout=30,
                        encoding="utf-8", errors="replace"
                    )
                )
            output = result.stdout + result.stderr
            if result.returncode != 0 and output.strip():
                return f"执行错误 (exit {result.returncode}):\n{output[:3000]}"
            return output[:3000] or "(无输出)"
        except subprocess.TimeoutExpired:
            return "执行超时（Python 代码 30 秒 / Shell 命令 120 秒）"
        except FileNotFoundError:
            return "错误：找不到 python 命令"
        except Exception as e:
            return f"执行失败: {type(e).__name__}: {e}"

def register(registry):
    registry.register(CodeExecTool())
