"""受限代码执行器。

Docker 不可用时，本执行器提供可运行的本地受限执行路径。它依赖静态检查、
运行时路径守卫和可中断子进程，不等同于强隔离沙箱。
"""

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from backend.sandbox.security import SecurityPolicy


@dataclass
class SafeExecutionContext:
    """受限执行上下文。"""

    session_id: str
    input_dir: Path
    workspace_dir: Path
    output_dir: Path
    input_files: list[Path] = field(default_factory=list)


@dataclass
class SafeExecutionResult:
    """受限执行结果。"""

    success: bool
    output: str
    error: str
    code: str
    execution_time: float
    artifacts: dict[str, object] = field(default_factory=dict)


class SafeCodeExecutor:
    """本地受限代码执行器。"""

    def __init__(
        self,
        context: SafeExecutionContext,
        security_policy: SecurityPolicy | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> None:
        self.context = context
        self.security_policy = security_policy or SecurityPolicy()
        self.should_cancel = should_cancel

    def execute(self, code: str, timeout: int = 60) -> SafeExecutionResult:
        """执行代码并限制文件访问范围。"""
        allowed, reason = self.security_policy.is_execution_allowed(code)
        if not allowed:
            return SafeExecutionResult(
                success=False,
                output="",
                error=reason,
                code=code,
                execution_time=0.0,
                artifacts=self._collect_artifacts(),
            )

        self.context.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.context.output_dir.mkdir(parents=True, exist_ok=True)

        script_path = (self.context.workspace_dir / f"analysis_{int(time.time() * 1000)}.py").resolve()
        full_code = self._build_guard_preamble() + "\n\n" + code
        script_path.write_text(full_code, encoding="utf-8")

        start_time = time.time()
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["MPLCONFIGDIR"] = str((self.context.workspace_dir / ".matplotlib").resolve())
        env["PUBHAGENT_SESSION_ID"] = self.context.session_id

        process: subprocess.Popen[str] | None = None
        try:
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                errors="replace",
                text=True,
                cwd=str(self.context.workspace_dir),
                env=env,
                creationflags=creationflags,
            )

            while process.poll() is None:
                if self.should_cancel and self.should_cancel():
                    stdout, stderr = self._stop_process(process)
                    return self._build_result(
                        success=False,
                        output=stdout,
                        error="执行已被用户中断",
                        code=code,
                        start_time=start_time,
                        script_path=script_path,
                        stderr=stderr,
                    )

                if time.time() - start_time > timeout:
                    stdout, stderr = self._stop_process(process)
                    return self._build_result(
                        success=False,
                        output=stdout,
                        error=f"执行超时（{timeout} 秒）",
                        code=code,
                        start_time=start_time,
                        script_path=script_path,
                        stderr=stderr,
                    )

                time.sleep(0.1)

            stdout, stderr = process.communicate()
            return self._build_result(
                success=process.returncode == 0,
                output=stdout or "",
                error=stderr or "",
                code=code,
                start_time=start_time,
                script_path=script_path,
            )
        except Exception as exc:
            if process and process.poll() is None:
                self._stop_process(process)
            return SafeExecutionResult(
                success=False,
                output="",
                error=f"执行失败: {exc}",
                code=code,
                execution_time=time.time() - start_time,
                artifacts=self._collect_artifacts(),
            )

    def _build_guard_preamble(self) -> str:
        """生成运行时路径守卫代码。"""
        read_roots = [
            str(self.context.input_dir.resolve()),
            str(self.context.workspace_dir.resolve()),
            str(self.context.output_dir.resolve()),
        ]
        write_roots = [
            str(self.context.workspace_dir.resolve()),
            str(self.context.output_dir.resolve()),
        ]
        input_files = [str(path.resolve()) for path in self.context.input_files]

        return f'''
from pathlib import Path as _PH_Path
import builtins as _PH_builtins

PH_INPUT_DIR = r"{str(self.context.input_dir.resolve())}"
PH_WORKSPACE_DIR = r"{str(self.context.workspace_dir.resolve())}"
PH_OUTPUT_DIR = r"{str(self.context.output_dir.resolve())}"
PH_INPUT_FILES = {json.dumps(input_files, ensure_ascii=False)}
_PH_ALLOWED_READ_ROOTS = [r for r in {json.dumps(read_roots, ensure_ascii=False)}]
_PH_ALLOWED_WRITE_ROOTS = [r for r in {json.dumps(write_roots, ensure_ascii=False)}]

def _ph_is_relative(path, root):
    try:
        _PH_Path(path).resolve().relative_to(_PH_Path(root).resolve())
        return True
    except ValueError:
        return False

def _ph_check_path(file, mode="r"):
    if hasattr(file, "read") or hasattr(file, "write"):
        return file
    path = _PH_Path(file).expanduser().resolve()
    mode_text = str(mode)
    write_mode = any(flag in mode_text for flag in ("w", "a", "x", "+"))
    roots = _PH_ALLOWED_WRITE_ROOTS if write_mode else _PH_ALLOWED_READ_ROOTS
    if not any(_ph_is_relative(path, root) for root in roots):
        raise PermissionError(f"路径不在允许范围内: {{path}}")
    return path

_PH_ORIGINAL_OPEN = _PH_builtins.open
def _ph_safe_open(file, mode="r", *args, **kwargs):
    return _PH_ORIGINAL_OPEN(_ph_check_path(file, mode), mode, *args, **kwargs)
_PH_builtins.open = _ph_safe_open

_PH_ORIGINAL_PATH_OPEN = _PH_Path.open
def _ph_path_open(self, mode="r", *args, **kwargs):
    return _PH_ORIGINAL_PATH_OPEN(_ph_check_path(self, mode), mode, *args, **kwargs)
_PH_Path.open = _ph_path_open

_PH_ORIGINAL_READ_TEXT = _PH_Path.read_text
def _ph_read_text(self, *args, **kwargs):
    _ph_check_path(self, "r")
    return _PH_ORIGINAL_READ_TEXT(self, *args, **kwargs)
_PH_Path.read_text = _ph_read_text

_PH_ORIGINAL_READ_BYTES = _PH_Path.read_bytes
def _ph_read_bytes(self, *args, **kwargs):
    _ph_check_path(self, "rb")
    return _PH_ORIGINAL_READ_BYTES(self, *args, **kwargs)
_PH_Path.read_bytes = _ph_read_bytes

_PH_ORIGINAL_WRITE_TEXT = _PH_Path.write_text
def _ph_write_text(self, data, *args, **kwargs):
    _ph_check_path(self, "w")
    return _PH_ORIGINAL_WRITE_TEXT(self, data, *args, **kwargs)
_PH_Path.write_text = _ph_write_text

_PH_ORIGINAL_WRITE_BYTES = _PH_Path.write_bytes
def _ph_write_bytes(self, data, *args, **kwargs):
    _ph_check_path(self, "wb")
    return _PH_ORIGINAL_WRITE_BYTES(self, data, *args, **kwargs)
_PH_Path.write_bytes = _ph_write_bytes

_PH_ORIGINAL_MKDIR = _PH_Path.mkdir
def _ph_mkdir(self, *args, **kwargs):
    _ph_check_path(self, "w")
    return _PH_ORIGINAL_MKDIR(self, *args, **kwargs)
_PH_Path.mkdir = _ph_mkdir

_PH_ORIGINAL_TOUCH = _PH_Path.touch
def _ph_touch(self, *args, **kwargs):
    _ph_check_path(self, "w")
    return _PH_ORIGINAL_TOUCH(self, *args, **kwargs)
_PH_Path.touch = _ph_touch

_PH_ORIGINAL_UNLINK = _PH_Path.unlink
def _ph_unlink(self, *args, **kwargs):
    _ph_check_path(self, "w")
    return _PH_ORIGINAL_UNLINK(self, *args, **kwargs)
_PH_Path.unlink = _ph_unlink

_PH_ORIGINAL_ITERDIR = _PH_Path.iterdir
def _ph_iterdir(self):
    _ph_check_path(self, "r")
    return _PH_ORIGINAL_ITERDIR(self)
_PH_Path.iterdir = _ph_iterdir

_PH_ORIGINAL_GLOB = _PH_Path.glob
def _ph_glob(self, pattern):
    _ph_check_path(self, "r")
    return _PH_ORIGINAL_GLOB(self, pattern)
_PH_Path.glob = _ph_glob

_PH_ORIGINAL_RGLOB = _PH_Path.rglob
def _ph_rglob(self, pattern):
    _ph_check_path(self, "r")
    return _PH_ORIGINAL_RGLOB(self, pattern)
_PH_Path.rglob = _ph_rglob

_PH_ORIGINAL_EXISTS = _PH_Path.exists
def _ph_exists(self):
    _ph_check_path(self, "r")
    return _PH_ORIGINAL_EXISTS(self)
_PH_Path.exists = _ph_exists

_PH_ORIGINAL_STAT = _PH_Path.stat
def _ph_stat(self, *args, **kwargs):
    _ph_check_path(self, "r")
    return _PH_ORIGINAL_STAT(self, *args, **kwargs)
_PH_Path.stat = _ph_stat

_PH_ORIGINAL_IS_FILE = _PH_Path.is_file
def _ph_is_file(self):
    _ph_check_path(self, "r")
    return _PH_ORIGINAL_IS_FILE(self)
_PH_Path.is_file = _ph_is_file

_PH_ORIGINAL_IS_DIR = _PH_Path.is_dir
def _ph_is_dir(self):
    _ph_check_path(self, "r")
    return _PH_ORIGINAL_IS_DIR(self)
_PH_Path.is_dir = _ph_is_dir
'''

    def _collect_artifacts(self) -> dict[str, object]:
        """收集输出目录产物。"""
        output_files = []
        if self.context.output_dir.exists():
            output_files = [
                str(path.resolve())
                for path in self.context.output_dir.rglob("*")
                if path.is_file()
            ]
        return {
            "output_dir": str(self.context.output_dir.resolve()),
            "workspace_dir": str(self.context.workspace_dir.resolve()),
            "input_files": [str(path.resolve()) for path in self.context.input_files],
            "output_files": output_files,
        }

    def _stop_process(self, process: subprocess.Popen[str]) -> tuple[str, str]:
        """终止子进程并回收输出。"""
        try:
            process.kill()
        except Exception:
            process.terminate()

        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()

        return stdout or "", stderr or ""

    def _build_result(
        self,
        *,
        success: bool,
        output: str,
        error: str,
        code: str,
        start_time: float,
        script_path: Path,
        stderr: str = "",
    ) -> SafeExecutionResult:
        """统一构造执行结果。"""
        artifacts = self._collect_artifacts()
        artifacts["script_path"] = str(script_path)
        final_error = error
        if stderr and stderr not in final_error:
            final_error = f"{final_error}\n{stderr}".strip()

        return SafeExecutionResult(
            success=success,
            output=self._truncate(output),
            error=self._truncate(final_error),
            code=code,
            execution_time=time.time() - start_time,
            artifacts=artifacts,
        )

    def _truncate(self, text: str, limit: int = 20000) -> str:
        """截断过长输出。"""
        if len(text) <= limit:
            return text
        return text[:limit] + "\n... [输出已截断]"
