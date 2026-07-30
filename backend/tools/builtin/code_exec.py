import os
import subprocess
import sys
import threading
import time
from tools.base import BaseTool


class ShellSession:
    """持久化 Shell 会话：保持 cwd、env、进程"""

    def __init__(self):
        self.process = None
        self.cwd = os.getcwd()
        self._lock = threading.Lock()
        self._start()

    def _start(self):
        """启动持久 shell 进程"""
        if self.process and self.process.poll() is None:
            return  # 已经在运行

        env = os.environ.copy()
        if os.name == 'nt':
            self.process = subprocess.Popen(
                ['cmd.exe', '/K', 'chcp 65001 >nul'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self.cwd,
                env=env,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
            )
        else:
            self.process = subprocess.Popen(
                ['bash', '--norc', '--noprofile'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self.cwd,
                env=env,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
            )
        # 读取启动 banner
        time.sleep(0.2)

    def execute(self, command: str, timeout: int = 30) -> str:
        """发送命令到持久 shell，返回输出"""
        with self._lock:
            if self.process.poll() is not None:
                self._start()

            marker = f"__DONE_{os.getpid()}_{int(time.time()*1000)}__"

            # 更新 cwd（如果命令包含 cd）
            self._update_cwd(command)

            try:
                # 发送命令 + echo marker
                cmd = f"{command}\necho {marker}\n"
                self.process.stdin.write(cmd)
                self.process.stdin.flush()

                # 读取输出直到 marker
                output_lines = []
                deadline = time.time() + timeout

                while time.time() < deadline:
                    try:
                        # 非阻塞读取（用线程超时）
                        line = self._readline_with_timeout(deadline - time.time())
                        if line is None:
                            break
                        if marker in line:
                            break
                        output_lines.append(line)
                    except Exception:
                        break

                output = ''.join(output_lines)
                # 去掉尾部空行
                output = output.rstrip('\n')
                return output if output else '(无输出)'

            except Exception as e:
                return f"Shell 执行失败: {e}"

    def _readline_with_timeout(self, timeout: float) -> str | None:
        """带超时的 readline"""
        result = [None]

        def _read():
            try:
                result[0] = self.process.stdout.readline()
            except Exception:
                result[0] = None

        t = threading.Thread(target=_read, daemon=True)
        t.start()
        t.join(timeout=max(0.1, timeout))
        if t.is_alive():
            return None
        return result[0]

    def _update_cwd(self, command: str):
        """解析 cd 命令更新工作目录"""
        cmd = command.strip()
        if cmd.startswith('cd '):
            target = cmd[3:].strip().strip('"').strip("'")
            if target:
                new_cwd = os.path.normpath(os.path.join(self.cwd, target))
                if os.path.isdir(new_cwd):
                    self.cwd = new_cwd
                    # 同步到子进程
                    if self.process.poll() is None:
                        try:
                            self.process.stdin.write(f'cd "{new_cwd}"\n')
                            self.process.stdin.flush()
                        except Exception:
                            pass

    def close(self):
        """关闭 shell 进程"""
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write('exit\n')
                self.process.stdin.flush()
                self.process.wait(timeout=3)
            except Exception:
                self.process.kill()


# 全局 shell 会话
_shell_session = None


def _get_shell():
    global _shell_session
    if _shell_session is None:
        _shell_session = ShellSession()
    return _shell_session


class CodeExecTool(BaseTool):
    name = "code_exec"
    description = "执行 Python 代码或 shell 命令并返回输出。Shell 命令会保持工作目录和环境变量。"
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "要执行的 Python 代码或 shell 命令"},
            "cwd": {"type": "string", "description": "工作目录（可选，不填则使用当前目录）"}
        },
        "required": ["code"]
    }

    async def execute(self, code: str = "", base64_content: str = "", save_to: str = "", cwd: str = "", **kwargs) -> str:
        import base64 as b64

        # base64 写入大文件模式
        if base64_content and save_to:
            try:
                data = b64.b64decode(base64_content)
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

        # 判断是否是 Python 代码
        is_python = self._is_python(code)

        try:
            loop = __import__('asyncio').get_event_loop()

            if is_python:
                # Python 代码：每次独立执行
                result = await loop.run_in_executor(
                    None,
                    lambda: subprocess.run(
                        [sys.executable, "-c", code],
                        capture_output=True, text=True, timeout=30,
                        encoding="utf-8", errors="replace",
                        cwd=cwd or _get_shell().cwd
                    )
                )
                output = result.stdout + result.stderr
                if result.returncode != 0 and output.strip():
                    return f"执行错误 (exit {result.returncode}):\n{output[:3000]}"
                return output[:3000] or "(无输出)"
            else:
                # Shell 命令：使用持久会话
                shell = _get_shell()
                if cwd:
                    shell.cwd = os.path.normpath(os.path.join(shell.cwd, cwd)) if not os.path.isabs(cwd) else cwd
                output = shell.execute(code, timeout=120)
                return output[:3000]

        except subprocess.TimeoutExpired:
            return "执行超时（Python 代码 30 秒 / Shell 命令 120 秒）"
        except FileNotFoundError:
            return "错误：找不到 python 命令"
        except Exception as e:
            return f"执行失败: {type(e).__name__}: {e}"

    @staticmethod
    def _is_python(code: str) -> bool:
        """简单判断是否是 Python 代码"""
        # 如果有明显的 Python 语法，认为是 Python
        python_indicators = ['import ', 'from ', 'def ', 'class ', 'print(', 'if __name__', 'for ', 'while ', 'try:', 'with ']
        shell_indicators = ['git ', 'pip ', 'npm ', 'cd ', 'mkdir ', 'rm ', 'cp ', 'mv ',
                           'ls ', 'dir ', 'cat ', 'echo ', 'curl ', 'wget ', 'apt ',
                           'sudo ', 'docker ', 'python ', 'node ']

        first_line = code.split('\n')[0].strip()

        # 明确的 shell 命令
        for cmd in shell_indicators:
            if first_line.startswith(cmd):
                return False

        # 明确的 Python
        for ind in python_indicators:
            if ind in code[:200]:
                return True

        # 默认当作 shell
        return False


def register(registry):
    registry.register(CodeExecTool())
