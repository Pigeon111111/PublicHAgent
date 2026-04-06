"""工具安全守卫

提供工具权限检查、参数验证、执行日志记录、异常捕获等功能。
"""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.tools.base import BaseTool, ToolError


class ToolGuardError(Exception):
    """工具安全守卫错误"""

    pass


@dataclass
class ExecutionLog:
    """执行日志"""

    tool_name: str
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float | None = None
    success: bool = False
    error: str | None = None
    error_type: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    resource_usage: dict[str, float] = field(default_factory=dict)


@dataclass
class SecurityPolicy:
    """安全策略配置"""

    allowed_paths: list[str] = field(default_factory=lambda: ["."])
    blocked_paths: list[str] = field(default_factory=lambda: [])
    blocked_extensions: list[str] = field(
        default_factory=lambda: [".exe", ".bat", ".cmd", ".sh", ".ps1", ".vbs", ".js"]
    )
    blocked_operations: list[str] = field(default_factory=lambda: [])
    max_file_size_mb: float = 100.0
    max_execution_time_seconds: float = 300.0
    max_memory_mb: float = 1024.0
    allow_network: bool = False
    allow_subprocess: bool = False
    allow_file_write: bool = True
    allow_file_delete: bool = False
    allowed_domains: list[str] = field(default_factory=list)
    sensitive_patterns: list[str] = field(
        default_factory=lambda: [
            r"password",
            r"secret",
            r"api_key",
            r"token",
            r"credential",
        ]
    )

    def is_path_allowed(self, path: str) -> tuple[bool, str]:
        """检查路径是否被允许访问"""
        try:
            abs_path = Path(path).resolve()
        except Exception:
            return False, f"无效路径: {path}"

        for blocked in self.blocked_paths:
            blocked_resolved = Path(blocked).resolve()
            try:
                abs_path.relative_to(blocked_resolved)
                return False, f"路径被阻止: {path}"
            except ValueError:
                pass

        if not self.allowed_paths:
            return True, ""

        for allowed in self.allowed_paths:
            allowed_resolved = Path(allowed).resolve()
            try:
                abs_path.relative_to(allowed_resolved)
                return True, ""
            except ValueError:
                pass

        return False, f"路径不在允许范围内: {path}"

    def is_extension_allowed(self, path: str) -> tuple[bool, str]:
        """检查文件扩展名是否被允许"""
        ext = Path(path).suffix.lower()
        if ext in self.blocked_extensions:
            return False, f"禁止访问的文件类型: {ext}"
        return True, ""

    def contains_sensitive_data(self, data: Any) -> tuple[bool, str]:
        """检查数据是否包含敏感信息"""
        if data is None:
            return False, ""

        data_str = str(data)
        for pattern in self.sensitive_patterns:
            if re.search(pattern, data_str, re.IGNORECASE):
                return True, f"检测到敏感数据模式: {pattern}"
        return False, ""

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, list[str]]:
        """验证参数"""
        errors = []

        for key, value in params.items():
            if key in ["file_path", "path", "output_path", "directory"]:
                is_allowed, msg = self.is_path_allowed(str(value))
                if not is_allowed:
                    errors.append(msg)

                is_ext_allowed, ext_msg = self.is_extension_allowed(str(value))
                if not is_ext_allowed:
                    errors.append(ext_msg)

            if key in ["content", "data"]:
                has_sensitive, msg = self.contains_sensitive_data(value)
                if has_sensitive:
                    errors.append(msg)

        return len(errors) == 0, errors


class ToolGuard:
    """工具安全守卫

    拦截所有工具执行，进行权限检查、参数验证、执行监控。
    """

    def __init__(self, policy: SecurityPolicy | None = None) -> None:
        """初始化安全守卫

        Args:
            policy: 安全策略，如果为 None 则使用默认策略
        """
        self.policy = policy or SecurityPolicy()
        self._execution_logs: list[ExecutionLog] = []
        self._max_logs: int = 1000

    def check_permission(self, tool: BaseTool, operation: str) -> tuple[bool, str]:
        """检查工具权限

        Args:
            tool: 工具实例
            operation: 操作类型

        Returns:
            (是否允许, 原因)
        """
        tool_name = tool.name

        if tool_name in self.policy.blocked_operations:
            return False, f"工具被禁止: {tool_name}"

        if "write" in tool_name and not self.policy.allow_file_write:
            return False, "文件写入操作被禁止"

        if "delete" in tool_name and not self.policy.allow_file_delete:
            return False, "文件删除操作被禁止"

        if "network" in tool_name and not self.policy.allow_network:
            return False, "网络操作被禁止"

        if "subprocess" in tool_name and not self.policy.allow_subprocess:
            return False, "子进程操作被禁止"

        return True, ""

    def validate_args(
        self, tool: BaseTool, args: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """验证工具参数

        Args:
            tool: 工具实例
            args: 参数字典

        Returns:
            (是否有效, 错误列表)
        """
        errors = []

        try:
            validated = tool.validate_args(**args)
            args = validated.model_dump()
        except ToolError as e:
            errors.append(str(e))
            return False, errors

        is_valid, policy_errors = self.policy.validate_params(args)
        errors.extend(policy_errors)

        return len(errors) == 0, errors

    def execute_with_guard(
        self,
        tool: BaseTool,
        args: dict[str, Any],
        pre_hook: Callable[[str, dict[str, Any]], None] | None = None,
        post_hook: Callable[[str, dict[str, Any], Any], None] | None = None,
    ) -> Any:
        """带安全守卫的工具执行

        Args:
            tool: 工具实例
            args: 参数字典
            pre_hook: 执行前钩子
            post_hook: 执行后钩子

        Returns:
            执行结果

        Raises:
            ToolGuardError: 安全检查失败
            ToolError: 工具执行失败
        """
        log = ExecutionLog(
            tool_name=tool.name,
            start_time=datetime.now(),
            params=self._sanitize_params(args),
        )

        try:
            is_allowed, reason = self.check_permission(tool, "execute")
            if not is_allowed:
                raise ToolGuardError(f"权限检查失败: {reason}")

            is_valid, errors = self.validate_args(tool, args)
            if not is_valid:
                raise ToolGuardError(f"参数验证失败: {'; '.join(errors)}")

            if pre_hook:
                pre_hook(tool.name, args)

            start_time = time.time()
            result = tool.run(**args)
            end_time = time.time()

            log.duration_ms = (end_time - start_time) * 1000
            log.success = True
            log.result = self._sanitize_result(result)

            if log.duration_ms > self.policy.max_execution_time_seconds * 1000:
                log.error = f"执行时间超过限制: {log.duration_ms:.2f}ms"
                log.error_type = "TimeoutWarning"

            if post_hook:
                post_hook(tool.name, args, result)

            return result

        except ToolGuardError:
            log.success = False
            log.error_type = "ToolGuardError"
            raise
        except ToolError as e:
            log.success = False
            log.error = str(e)
            log.error_type = "ToolError"
            raise
        except Exception as e:
            log.success = False
            log.error = f"{type(e).__name__}: {str(e)}"
            log.error_type = type(e).__name__
            raise ToolError(f"工具执行异常: {e}") from e
        finally:
            log.end_time = datetime.now()
            self._add_log(log)

    def _sanitize_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """清理参数中的敏感信息"""
        sanitized = {}
        for key, value in params.items():
            has_sensitive, _ = self.policy.contains_sensitive_data(value)
            if has_sensitive:
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, str) and len(value) > 100:
                sanitized[key] = value[:100] + "..."
            else:
                sanitized[key] = value
        return sanitized

    def _sanitize_result(self, result: Any) -> Any:
        """清理结果中的敏感信息"""
        has_sensitive, _ = self.policy.contains_sensitive_data(result)
        if has_sensitive:
            return "***REDACTED***"
        if isinstance(result, str) and len(result) > 500:
            return result[:500] + "..."
        return result

    def _add_log(self, log: ExecutionLog) -> None:
        """添加执行日志"""
        self._execution_logs.append(log)
        if len(self._execution_logs) > self._max_logs:
            self._execution_logs = self._execution_logs[-self._max_logs :]

    def get_logs(
        self,
        tool_name: str | None = None,
        success_only: bool = False,
        error_only: bool = False,
        limit: int = 100,
    ) -> list[ExecutionLog]:
        """获取执行日志

        Args:
            tool_name: 过滤工具名称
            success_only: 仅返回成功的日志
            error_only: 仅返回失败的日志
            limit: 返回数量限制

        Returns:
            日志列表
        """
        logs = self._execution_logs

        if tool_name:
            logs = [log for log in logs if log.tool_name == tool_name]

        if success_only:
            logs = [log for log in logs if log.success]

        if error_only:
            logs = [log for log in logs if not log.success]

        return logs[-limit:]

    def get_statistics(self) -> dict[str, Any]:
        """获取执行统计信息"""
        logs = self._execution_logs

        if not logs:
            return {
                "total_executions": 0,
                "successful": 0,
                "failed": 0,
                "success_rate": 0.0,
                "avg_duration_ms": 0.0,
                "tools_used": [],
            }

        successful = sum(1 for log in logs if log.success)
        durations = [log.duration_ms for log in logs if log.duration_ms is not None]
        tools = {log.tool_name for log in logs}

        return {
            "total_executions": len(logs),
            "successful": successful,
            "failed": len(logs) - successful,
            "success_rate": successful / len(logs) * 100,
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
            "min_duration_ms": min(durations) if durations else 0,
            "tools_used": list(tools),
            "error_types": self._get_error_types(logs),
        }

    def _get_error_types(self, logs: list[ExecutionLog]) -> dict[str, int]:
        """获取错误类型统计"""
        error_types: dict[str, int] = {}
        for log in logs:
            if log.error_type:
                error_types[log.error_type] = error_types.get(log.error_type, 0) + 1
        return error_types

    def clear_logs(self) -> None:
        """清空执行日志"""
        self._execution_logs.clear()

    def wrap_tool(self, tool: BaseTool) -> Callable[[dict[str, Any]], Any]:
        """包装工具，返回带安全守卫的执行函数

        Args:
            tool: 工具实例

        Returns:
            包装后的执行函数
        """

        def wrapped(**kwargs: Any) -> Any:
            return self.execute_with_guard(tool, kwargs)

        wrapped.__name__ = f"guarded_{tool.name}"
        wrapped.__doc__ = tool.description
        return wrapped  # type: ignore[return-value]
