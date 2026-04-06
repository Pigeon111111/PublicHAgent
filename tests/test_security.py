"""安全守卫模块单元测试"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel, Field

from backend.tools.base import BaseTool, ToolError
from backend.tools.security import ExecutionLog, SecurityPolicy, ToolGuard, ToolGuardError


class MockToolArgs(BaseModel):
    """模拟工具参数"""

    file_path: str = Field(..., description="文件路径")
    content: str = Field(default="", description="内容")


class MockTool(BaseTool):
    """模拟工具"""

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "模拟工具"

    @property
    def args_schema(self) -> type[BaseModel]:
        return MockToolArgs

    def run(self, **kwargs) -> str:
        return "success"


class MockWriteTool(BaseTool):
    """模拟写入工具"""

    @property
    def name(self) -> str:
        return "write_data"

    @property
    def description(self) -> str:
        return "写入数据"

    @property
    def args_schema(self) -> type[BaseModel]:
        return MockToolArgs

    def run(self, **kwargs) -> str:
        return "written"


class MockDeleteTool(BaseTool):
    """模拟删除工具"""

    @property
    def name(self) -> str:
        return "delete_file"

    @property
    def description(self) -> str:
        return "删除文件"

    @property
    def args_schema(self) -> type[BaseModel]:
        return MockToolArgs

    def run(self, **kwargs) -> str:
        return "deleted"


class MockNetworkTool(BaseTool):
    """模拟网络工具"""

    @property
    def name(self) -> str:
        return "network_request"

    @property
    def description(self) -> str:
        return "网络请求"

    @property
    def args_schema(self) -> type[BaseModel]:
        return MockToolArgs

    def run(self, **kwargs) -> str:
        return "networked"


class TestSecurityPolicy:
    """测试 SecurityPolicy"""

    def test_default_policy(self) -> None:
        """测试默认策略"""
        policy = SecurityPolicy()

        assert policy.allow_file_write is True
        assert policy.allow_file_delete is False
        assert policy.allow_network is False
        assert ".exe" in policy.blocked_extensions

    def test_is_path_allowed(self) -> None:
        """测试路径允许检查"""
        policy = SecurityPolicy(allowed_paths=["/safe/path"])

        is_allowed, _ = policy.is_path_allowed("/safe/path/file.txt")
        assert is_allowed is True

        is_allowed, msg = policy.is_path_allowed("/unsafe/path/file.txt")
        assert is_allowed is False
        assert "不在允许范围内" in msg

    def test_is_path_blocked(self) -> None:
        """测试路径阻止检查"""
        policy = SecurityPolicy(blocked_paths=["/blocked"])

        is_allowed, msg = policy.is_path_allowed("/blocked/file.txt")
        assert is_allowed is False
        assert "被阻止" in msg

    def test_is_extension_allowed(self) -> None:
        """测试扩展名检查"""
        policy = SecurityPolicy()

        is_allowed, _ = policy.is_extension_allowed("file.txt")
        assert is_allowed is True

        is_allowed, msg = policy.is_extension_allowed("malware.exe")
        assert is_allowed is False
        assert "禁止访问的文件类型" in msg

    def test_contains_sensitive_data(self) -> None:
        """测试敏感数据检测"""
        policy = SecurityPolicy()

        has_sensitive, _ = policy.contains_sensitive_data("normal data")
        assert has_sensitive is False

        has_sensitive, msg = policy.contains_sensitive_data("password=secret123")
        assert has_sensitive is True
        assert "敏感数据" in msg

        has_sensitive, msg = policy.contains_sensitive_data("api_key=abc123")
        assert has_sensitive is True

    def test_validate_params(self) -> None:
        """测试参数验证"""
        policy = SecurityPolicy(allowed_paths=["/safe"])

        is_valid, errors = policy.validate_params({"file_path": "/safe/file.txt"})
        assert is_valid is True
        assert len(errors) == 0

        is_valid, errors = policy.validate_params({"file_path": "/unsafe/file.exe"})
        assert is_valid is False
        assert len(errors) > 0


class TestToolGuard:
    """测试 ToolGuard"""

    def test_init(self) -> None:
        """测试初始化"""
        guard = ToolGuard()
        assert guard.policy is not None

        custom_policy = SecurityPolicy(allow_network=True)
        guard = ToolGuard(policy=custom_policy)
        assert guard.policy.allow_network is True

    def test_check_permission_allowed(self) -> None:
        """测试权限检查 - 允许"""
        guard = ToolGuard()
        tool = MockTool()

        is_allowed, _ = guard.check_permission(tool, "execute")
        assert is_allowed is True

    def test_check_permission_blocked_tool(self) -> None:
        """测试权限检查 - 工具被阻止"""
        policy = SecurityPolicy(blocked_operations=["mock_tool"])
        guard = ToolGuard(policy=policy)
        tool = MockTool()

        is_allowed, msg = guard.check_permission(tool, "execute")
        assert is_allowed is False
        assert "工具被禁止" in msg

    def test_check_permission_write_blocked(self) -> None:
        """测试权限检查 - 写入被阻止"""
        policy = SecurityPolicy(allow_file_write=False)
        guard = ToolGuard(policy=policy)
        tool = MockWriteTool()

        is_allowed, msg = guard.check_permission(tool, "execute")
        assert is_allowed is False
        assert "文件写入操作被禁止" in msg

    def test_check_permission_delete_blocked(self) -> None:
        """测试权限检查 - 删除被阻止"""
        policy = SecurityPolicy(allow_file_delete=False)
        guard = ToolGuard(policy=policy)
        tool = MockDeleteTool()

        is_allowed, msg = guard.check_permission(tool, "execute")
        assert is_allowed is False
        assert "文件删除操作被禁止" in msg

    def test_check_permission_network_blocked(self) -> None:
        """测试权限检查 - 网络被阻止"""
        policy = SecurityPolicy(allow_network=False)
        guard = ToolGuard(policy=policy)
        tool = MockNetworkTool()

        is_allowed, msg = guard.check_permission(tool, "execute")
        assert is_allowed is False
        assert "网络操作被禁止" in msg

    def test_validate_args_success(self) -> None:
        """测试参数验证成功"""
        policy = SecurityPolicy(allowed_paths=["/safe"])
        guard = ToolGuard(policy=policy)
        tool = MockTool()

        is_valid, errors = guard.validate_args(tool, {"file_path": "/safe/file.txt"})
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_args_path_not_allowed(self) -> None:
        """测试参数验证 - 路径不允许"""
        policy = SecurityPolicy(allowed_paths=["/safe"])
        guard = ToolGuard(policy=policy)
        tool = MockTool()

        is_valid, errors = guard.validate_args(tool, {"file_path": "/unsafe/file.txt"})
        assert is_valid is False
        assert any("不在允许范围内" in e for e in errors)

    def test_validate_args_missing_required(self) -> None:
        """测试参数验证 - 缺少必需参数"""
        guard = ToolGuard()
        tool = MockTool()

        is_valid, errors = guard.validate_args(tool, {})
        assert is_valid is False
        assert len(errors) > 0

    def test_execute_with_guard_success(self) -> None:
        """测试安全执行成功"""
        policy = SecurityPolicy(allowed_paths=["/safe"])
        guard = ToolGuard(policy=policy)
        tool = MockTool()

        result = guard.execute_with_guard(tool, {"file_path": "/safe/file.txt"})
        assert result == "success"

        logs = guard.get_logs()
        assert len(logs) == 1
        assert logs[0].success is True

    def test_execute_with_guard_permission_denied(self) -> None:
        """测试安全执行 - 权限拒绝"""
        policy = SecurityPolicy(blocked_operations=["mock_tool"])
        guard = ToolGuard(policy=policy)
        tool = MockTool()

        with pytest.raises(ToolGuardError, match="权限检查失败"):
            guard.execute_with_guard(tool, {"file_path": "/safe/file.txt"})

    def test_execute_with_guard_validation_failed(self) -> None:
        """测试安全执行 - 验证失败"""
        policy = SecurityPolicy(allowed_paths=["/safe"])
        guard = ToolGuard(policy=policy)
        tool = MockTool()

        with pytest.raises(ToolGuardError, match="参数验证失败"):
            guard.execute_with_guard(tool, {"file_path": "/unsafe/file.txt"})

    def test_execute_with_guard_tool_error(self) -> None:
        """测试安全执行 - 工具错误"""

        class ErrorTool(BaseTool):
            @property
            def name(self) -> str:
                return "error_tool"

            @property
            def description(self) -> str:
                return "错误工具"

            @property
            def args_schema(self) -> type[BaseModel]:
                return MockToolArgs

            def run(self, **kwargs) -> str:
                raise ToolError("工具执行错误")

        policy = SecurityPolicy(allowed_paths=["/safe"])
        guard = ToolGuard(policy=policy)
        tool = ErrorTool()

        with pytest.raises(ToolError, match="工具执行错误"):
            guard.execute_with_guard(tool, {"file_path": "/safe/file.txt"})

        logs = guard.get_logs()
        assert len(logs) == 1
        assert logs[0].success is False
        assert logs[0].error_type == "ToolError"

    def test_execute_with_hooks(self) -> None:
        """测试安全执行 - 钩子函数"""
        policy = SecurityPolicy(allowed_paths=["/safe"])
        guard = ToolGuard(policy=policy)
        tool = MockTool()

        pre_called = []
        post_called = []

        def pre_hook(name: str, args: dict) -> None:
            pre_called.append((name, args))

        def post_hook(name: str, args: dict, result: str) -> None:
            post_called.append((name, args, result))

        guard.execute_with_guard(
            tool,
            {"file_path": "/safe/file.txt"},
            pre_hook=pre_hook,
            post_hook=post_hook,
        )

        assert len(pre_called) == 1
        assert len(post_called) == 1
        assert post_called[0][2] == "success"

    def test_get_logs(self) -> None:
        """测试获取日志"""
        policy = SecurityPolicy(allowed_paths=["/safe"])
        guard = ToolGuard(policy=policy)
        tool = MockTool()

        guard.execute_with_guard(tool, {"file_path": "/safe/file1.txt"})
        guard.execute_with_guard(tool, {"file_path": "/safe/file2.txt"})

        logs = guard.get_logs()
        assert len(logs) == 2

        logs = guard.get_logs(limit=1)
        assert len(logs) == 1

    def test_get_logs_filter(self) -> None:
        """测试获取日志 - 过滤"""
        policy = SecurityPolicy(allowed_paths=["/safe"])
        guard = ToolGuard(policy=policy)
        tool = MockTool()

        guard.execute_with_guard(tool, {"file_path": "/safe/file.txt"})

        logs = guard.get_logs(success_only=True)
        assert len(logs) == 1

        logs = guard.get_logs(error_only=True)
        assert len(logs) == 0

    def test_get_statistics(self) -> None:
        """测试获取统计信息"""
        policy = SecurityPolicy(allowed_paths=["/safe"])
        guard = ToolGuard(policy=policy)
        tool = MockTool()

        guard.execute_with_guard(tool, {"file_path": "/safe/file1.txt"})
        guard.execute_with_guard(tool, {"file_path": "/safe/file2.txt"})

        stats = guard.get_statistics()
        assert stats["total_executions"] == 2
        assert stats["successful"] == 2
        assert stats["failed"] == 0
        assert stats["success_rate"] == 100.0
        assert "mock_tool" in stats["tools_used"]

    def test_clear_logs(self) -> None:
        """测试清空日志"""
        policy = SecurityPolicy(allowed_paths=["/safe"])
        guard = ToolGuard(policy=policy)
        tool = MockTool()

        guard.execute_with_guard(tool, {"file_path": "/safe/file.txt"})
        assert len(guard.get_logs()) == 1

        guard.clear_logs()
        assert len(guard.get_logs()) == 0

    def test_wrap_tool(self) -> None:
        """测试包装工具"""
        policy = SecurityPolicy(allowed_paths=["/safe"])
        guard = ToolGuard(policy=policy)
        tool = MockTool()

        wrapped = guard.wrap_tool(tool)
        result = wrapped(file_path="/safe/file.txt")

        assert result == "success"
        assert len(guard.get_logs()) == 1

    def test_sensitive_params_sanitized(self) -> None:
        """测试敏感参数清理"""
        policy = SecurityPolicy(allowed_paths=["/safe"], sensitive_patterns=[])
        guard = ToolGuard(policy=policy)
        tool = MockTool()

        guard.execute_with_guard(
            tool,
            {"file_path": "/safe/file.txt", "content": "password=secret123"},
        )

        logs = guard.get_logs()
        assert logs[0].success is True


class TestExecutionLog:
    """测试 ExecutionLog"""

    def test_execution_log_creation(self) -> None:
        """测试执行日志创建"""
        from datetime import datetime

        log = ExecutionLog(
            tool_name="test_tool",
            start_time=datetime.now(),
            params={"arg1": "value1"},
        )

        assert log.tool_name == "test_tool"
        assert log.success is False
        assert log.end_time is None

    def test_execution_log_with_result(self) -> None:
        """测试执行日志带结果"""
        from datetime import datetime

        log = ExecutionLog(
            tool_name="test_tool",
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_ms=100.5,
            success=True,
            result="test_result",
        )

        assert log.success is True
        assert log.duration_ms == 100.5


class TestToolGuardIntegration:
    """测试工具守卫集成"""

    def test_guard_with_real_tools(self, tmp_path: Path) -> None:
        """测试与真实工具集成"""
        from backend.tools.builtin import ReadFileTool, WriteFileTool

        policy = SecurityPolicy(allowed_paths=[str(tmp_path)])
        guard = ToolGuard(policy=policy)

        write_tool = WriteFileTool()
        test_file = tmp_path / "test.txt"

        result = guard.execute_with_guard(
            write_tool,
            {"file_path": str(test_file), "content": "test content"},
        )
        assert "成功写入文件" in result

        read_tool = ReadFileTool()
        result = guard.execute_with_guard(read_tool, {"file_path": str(test_file)})
        assert result == "test content"

        stats = guard.get_statistics()
        assert stats["total_executions"] == 2
        assert stats["successful"] == 2

    def test_guard_blocks_dangerous_operations(self, tmp_path: Path) -> None:
        """测试阻止危险操作"""
        from backend.tools.builtin import WriteFileTool

        policy = SecurityPolicy(
            allowed_paths=[str(tmp_path)],
            blocked_extensions=[".exe"],
        )
        guard = ToolGuard(policy=policy)

        write_tool = WriteFileTool()
        exe_file = tmp_path / "malware.exe"

        with pytest.raises(ToolGuardError, match="参数验证失败"):
            guard.execute_with_guard(
                write_tool,
                {"file_path": str(exe_file), "content": "malware"},
            )
