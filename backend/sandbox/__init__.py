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

__all__ = [
    "ContainerInfo",
    "ContainerStatus",
    "ExecutionResult",
    "SandboxConfig",
    "SandboxManager",
    "get_sandbox_manager",
]
