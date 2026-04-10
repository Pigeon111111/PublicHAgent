"""沙箱环境模块

提供 Docker 容器隔离的代码执行环境。
"""

from backend.sandbox.manager import (
    ContainerInfo,
    ContainerStatus,
    ExecutionResult,
    SandboxConfig,
    SandboxManager,
    get_sandbox_manager,
)
from backend.sandbox.safe_executor import (
    SafeCodeExecutor,
    SafeExecutionContext,
    SafeExecutionResult,
)

__all__ = [
    "ContainerInfo",
    "ContainerStatus",
    "ExecutionResult",
    "SandboxConfig",
    "SandboxManager",
    "get_sandbox_manager",
    "SafeCodeExecutor",
    "SafeExecutionContext",
    "SafeExecutionResult",
]
