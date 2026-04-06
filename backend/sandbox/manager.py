"""沙箱管理器

提供 Docker 容器生命周期管理、代码执行、容器池管理功能。
使用 Docker SDK for Python 进行容器操作。
"""

import asyncio
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any

import docker
from docker.errors import APIError, ContainerError, ImageNotFound
from docker.models.containers import Container

from backend.sandbox.security import SecurityPolicy, ExecutionLimits


class ContainerStatus(Enum):
    """容器状态枚举"""

    CREATING = "creating"
    RUNNING = "running"
    IDLE = "idle"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ExecutionResult:
    """代码执行结果"""

    success: bool
    output: str
    error: str
    execution_time: float
    exit_code: int = 0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "execution_time": self.execution_time,
            "exit_code": self.exit_code,
        }


@dataclass
class ContainerInfo:
    """容器信息"""

    container_id: str
    container: Container
    status: ContainerStatus
    created_at: float
    last_used: float
    execution_count: int = 0
    error_count: int = 0

    def is_healthy(self, max_idle_time: float = 300.0, max_executions: int = 100) -> bool:
        """检查容器是否健康

        Args:
            max_idle_time: 最大空闲时间（秒）
            max_executions: 最大执行次数

        Returns:
            容器是否健康
        """
        if self.status == ContainerStatus.ERROR:
            return False

        if self.execution_count >= max_executions:
            return False

        return self.error_count <= 5


@dataclass
class SandboxConfig:
    """沙箱配置"""

    image_name: str = "pubhagent-sandbox:latest"
    memory_limit: str = "512m"
    cpu_quota: int = 50000
    cpu_period: int = 100000
    timeout: int = 60
    network_disabled: bool = True
    max_containers: int = 5
    container_pool_size: int = 2
    workspace_path: str = "/sandbox/workspace"
    output_path: str = "/sandbox/output"


class SandboxManager:
    """沙箱管理器

    管理 Docker 容器的生命周期，提供代码执行功能。
    支持容器池复用、健康检查、超时处理。
    """

    def __init__(self, config: SandboxConfig | None = None) -> None:
        """初始化沙箱管理器

        Args:
            config: 沙箱配置
        """
        self._config = config or SandboxConfig()
        self._client: docker.DockerClient | None = None
        self._containers: dict[str, ContainerInfo] = {}
        self._pool_lock = asyncio.Lock()
        self._initialized = False
        
        # 初始化安全策略
        execution_limits = ExecutionLimits(
            timeout=self._config.timeout,
            memory_limit=self._config.memory_limit,
            cpu_limit=float(self._config.cpu_quota) / self._config.cpu_period,
        )
        self._security_policy = SecurityPolicy(limits=execution_limits)

    def _get_client(self) -> docker.DockerClient:
        """获取 Docker 客户端"""
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def initialize(self) -> bool:
        """初始化沙箱管理器

        Returns:
            初始化是否成功
        """
        try:
            client = self._get_client()
            client.ping()
            self._initialized = True
            
            # 预热容器池
            self._warmup_containers()
            
            return True
        except Exception as e:
            print(f"初始化沙箱管理器失败: {e}")
            self._initialized = False
            return False

    def _warmup_containers(self) -> None:
        """预热容器池

        在初始化时创建指定数量的容器，减少首次执行时的等待时间。
        """
        try:
            for _ in range(min(self._config.container_pool_size, self._config.max_containers)):
                if len(self._containers) < self._config.max_containers:
                    container_info = self._create_container()
                    container_info.status = ContainerStatus.IDLE
                    print(f"预热容器创建成功: {container_info.container_id}")
        except Exception as e:
            print(f"容器预热失败: {e}")

    def _create_container(self) -> ContainerInfo:
        """创建新容器

        Returns:
            容器信息
        """
        client = self._get_client()
        container_id = f"sandbox-{uuid.uuid4().hex[:8]}"

        try:
            container = client.containers.create(
                image=self._config.image_name,
                name=container_id,
                mem_limit=self._config.memory_limit,
                cpu_quota=self._config.cpu_quota,
                cpu_period=self._config.cpu_period,
                network_disabled=self._config.network_disabled,
                detach=True,
                tty=True,
                stdin_open=True,
                working_dir=self._config.workspace_path,
                volumes={},
                security_opt=["no-new-privileges"],
                read_only=False,
            )

            container.start()

            info = ContainerInfo(
                container_id=container_id,
                container=container,
                status=ContainerStatus.RUNNING,
                created_at=time.time(),
                last_used=time.time(),
            )

            self._containers[container_id] = info
            return info

        except ImageNotFound:
            raise RuntimeError(f"Docker 镜像不存在: {self._config.image_name}") from None
        except APIError as e:
            raise RuntimeError(f"创建容器失败: {e}") from e

    def _get_or_create_container(self) -> ContainerInfo:
        """获取或创建容器

        Returns:
            容器信息
        """
        for info in self._containers.values():
            if info.status == ContainerStatus.IDLE and info.is_healthy():
                info.status = ContainerStatus.RUNNING
                info.last_used = time.time()
                return info

        if len(self._containers) >= self._config.max_containers:
            self._cleanup_oldest_container()

        return self._create_container()

    def _cleanup_oldest_container(self) -> None:
        """清理最旧的容器"""
        if not self._containers:
            return

        oldest = min(self._containers.values(), key=lambda x: x.last_used)
        self._remove_container(oldest.container_id)

    def _remove_container(self, container_id: str) -> None:
        """移除容器

        Args:
            container_id: 容器 ID
        """
        if container_id not in self._containers:
            return

        info = self._containers[container_id]
        try:
            info.container.stop(timeout=5)
            info.container.remove(force=True)
        except Exception:
            pass

        del self._containers[container_id]

    def execute_code(
        self,
        code: str,
        timeout: int | None = None,
    ) -> ExecutionResult:
        """在沙箱中执行代码

        Args:
            code: 要执行的 Python 代码
            timeout: 超时时间（秒）

        Returns:
            执行结果
        """
        if not self._initialized and not self.initialize():
            return ExecutionResult(
                success=False,
                output="",
                error="沙箱管理器未初始化",
                execution_time=0.0,
            )

        if timeout is None:
            timeout = self._config.timeout
        
        # 安全检查
        allowed, reason = self._security_policy.is_execution_allowed(code)
        if not allowed:
            return ExecutionResult(
                success=False,
                output="",
                error=reason,
                execution_time=0.0,
            )

        start_time = time.time()
        container_info: ContainerInfo | None = None

        try:
            container_info = self._get_or_create_container()
            container = container_info.container

            cmd = ["python", "-c", code]

            exit_code, output = container.exec_run(
                cmd=cmd,
                workdir=self._config.workspace_path,
                demux=True,
            )

            execution_time = time.time() - start_time

            stdout = output[0].decode("utf-8") if output[0] else ""
            stderr = output[1].decode("utf-8") if output[1] else ""

            container_info.execution_count += 1
            container_info.last_used = time.time()

            if exit_code == 0:
                container_info.status = ContainerStatus.IDLE
                return ExecutionResult(
                    success=True,
                    output=self._security_policy.sanitize_output(stdout),
                    error="",
                    execution_time=execution_time,
                    exit_code=exit_code,
                )
            else:
                container_info.error_count += 1
                container_info.status = ContainerStatus.IDLE
                return ExecutionResult(
                    success=False,
                    output=self._security_policy.sanitize_output(stdout),
                    error=self._security_policy.create_safe_error_message(stderr),
                    execution_time=execution_time,
                    exit_code=exit_code,
                )

        except ContainerError as e:
            execution_time = time.time() - start_time
            if container_info:
                container_info.error_count += 1
                container_info.status = ContainerStatus.ERROR
            return ExecutionResult(
                success=False,
                output="",
                error=self._security_policy.create_safe_error_message(f"容器执行错误: {e}"),
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = time.time() - start_time
            if container_info:
                container_info.error_count += 1
                container_info.status = ContainerStatus.ERROR
            return ExecutionResult(
                success=False,
                output="",
                error=self._security_policy.create_safe_error_message(f"执行失败: {e}"),
                execution_time=execution_time,
            )

    async def execute_code_async(
        self,
        code: str,
        timeout: int | None = None,
    ) -> ExecutionResult:
        """异步执行代码

        Args:
            code: 要执行的 Python 代码
            timeout: 超时时间（秒）

        Returns:
            执行结果
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.execute_code(code, timeout),
        )

    def get_result(self, container_id: str) -> dict[str, Any] | None:
        """获取容器执行结果

        Args:
            container_id: 容器 ID

        Returns:
            执行结果字典
        """
        if container_id not in self._containers:
            return None

        info = self._containers[container_id]
        return {
            "container_id": container_id,
            "status": info.status.value,
            "execution_count": info.execution_count,
            "error_count": info.error_count,
            "created_at": info.created_at,
            "last_used": info.last_used,
        }

    def cleanup(self) -> None:
        """清理所有容器"""
        for container_id in list(self._containers.keys()):
            self._remove_container(container_id)

        self._containers.clear()

    def cleanup_unhealthy(self) -> int:
        """清理不健康的容器

        Returns:
            清理的容器数量
        """
        to_remove = [
            container_id
            for container_id, info in self._containers.items()
            if not info.is_healthy()
        ]

        for container_id in to_remove:
            self._remove_container(container_id)

        return len(to_remove)

    def get_pool_status(self) -> dict[str, Any]:
        """获取容器池状态

        Returns:
            容器池状态信息
        """
        return {
            "total_containers": len(self._containers),
            "max_containers": self._config.max_containers,
            "containers": [
                {
                    "container_id": info.container_id,
                    "status": info.status.value,
                    "execution_count": info.execution_count,
                    "error_count": info.error_count,
                    "is_healthy": info.is_healthy(),
                }
                for info in self._containers.values()
            ],
        }

    def __enter__(self) -> "SandboxManager":
        """上下文管理器入口"""
        self.initialize()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """上下文管理器出口"""
        self.cleanup()


_sandbox_manager: SandboxManager | None = None


def get_sandbox_manager() -> SandboxManager:
    """获取沙箱管理器单例"""
    global _sandbox_manager
    if _sandbox_manager is None:
        _sandbox_manager = SandboxManager()
    return _sandbox_manager
