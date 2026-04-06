"""沙箱管理器单元测试"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from backend.sandbox import (
    ContainerInfo,
    ContainerStatus,
    ExecutionResult,
    SandboxConfig,
    SandboxManager,
)
from backend.sandbox.manager import get_sandbox_manager


class TestSandboxConfig:
    """测试沙箱配置"""

    def test_default_config(self) -> None:
        """测试默认配置"""
        config = SandboxConfig()
        assert config.image_name == "pubhagent-sandbox:latest"
        assert config.memory_limit == "512m"
        assert config.timeout == 60
        assert config.network_disabled is True
        assert config.max_containers == 5

    def test_custom_config(self) -> None:
        """测试自定义配置"""
        config = SandboxConfig(
            image_name="custom-image:v1",
            memory_limit="1g",
            timeout=120,
            max_containers=10,
        )
        assert config.image_name == "custom-image:v1"
        assert config.memory_limit == "1g"
        assert config.timeout == 120
        assert config.max_containers == 10


class TestExecutionResult:
    """测试执行结果"""

    def test_success_result(self) -> None:
        """测试成功结果"""
        result = ExecutionResult(
            success=True,
            output="执行成功",
            error="",
            execution_time=0.5,
            exit_code=0,
        )
        assert result.success is True
        assert result.output == "执行成功"
        assert result.error == ""
        assert result.exit_code == 0

    def test_failure_result(self) -> None:
        """测试失败结果"""
        result = ExecutionResult(
            success=False,
            output="",
            error="NameError: name 'x' is not defined",
            execution_time=0.1,
            exit_code=1,
        )
        assert result.success is False
        assert result.error == "NameError: name 'x' is not defined"
        assert result.exit_code == 1

    def test_to_dict(self) -> None:
        """测试转换为字典"""
        result = ExecutionResult(
            success=True,
            output="test",
            error="",
            execution_time=1.0,
            exit_code=0,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["output"] == "test"
        assert d["execution_time"] == 1.0


class TestContainerInfo:
    """测试容器信息"""

    def test_container_info_creation(self) -> None:
        """测试创建容器信息"""
        mock_container = MagicMock()
        info = ContainerInfo(
            container_id="test-container",
            container=mock_container,
            status=ContainerStatus.RUNNING,
            created_at=1000.0,
            last_used=1000.0,
        )
        assert info.container_id == "test-container"
        assert info.status == ContainerStatus.RUNNING
        assert info.execution_count == 0
        assert info.error_count == 0

    def test_is_healthy(self) -> None:
        """测试健康检查"""
        mock_container = MagicMock()
        info = ContainerInfo(
            container_id="test",
            container=mock_container,
            status=ContainerStatus.IDLE,
            created_at=1000.0,
            last_used=1000.0,
        )
        assert info.is_healthy() is True

    def test_is_healthy_error_status(self) -> None:
        """测试错误状态不健康"""
        mock_container = MagicMock()
        info = ContainerInfo(
            container_id="test",
            container=mock_container,
            status=ContainerStatus.ERROR,
            created_at=1000.0,
            last_used=1000.0,
        )
        assert info.is_healthy() is False

    def test_is_healthy_too_many_errors(self) -> None:
        """测试错误次数过多不健康"""
        mock_container = MagicMock()
        info = ContainerInfo(
            container_id="test",
            container=mock_container,
            status=ContainerStatus.IDLE,
            created_at=1000.0,
            last_used=1000.0,
            error_count=10,
        )
        assert info.is_healthy() is False

    def test_is_healthy_too_many_executions(self) -> None:
        """测试执行次数过多不健康"""
        mock_container = MagicMock()
        info = ContainerInfo(
            container_id="test",
            container=mock_container,
            status=ContainerStatus.IDLE,
            created_at=1000.0,
            last_used=1000.0,
            execution_count=150,
        )
        assert info.is_healthy() is False


class TestSandboxManager:
    """测试沙箱管理器"""

    def test_init_default_config(self) -> None:
        """测试默认配置初始化"""
        manager = SandboxManager()
        assert manager._config is not None
        assert manager._initialized is False

    def test_init_custom_config(self) -> None:
        """测试自定义配置初始化"""
        config = SandboxConfig(timeout=120)
        manager = SandboxManager(config=config)
        assert manager._config.timeout == 120

    def test_get_pool_status_empty(self) -> None:
        """测试空池状态"""
        manager = SandboxManager()
        status = manager.get_pool_status()
        assert status["total_containers"] == 0
        assert status["max_containers"] == 5

    def test_cleanup_empty(self) -> None:
        """测试清理空容器池"""
        manager = SandboxManager()
        manager.cleanup()
        assert len(manager._containers) == 0

    def test_cleanup_unhealthy_empty(self) -> None:
        """测试清理不健康容器（空）"""
        manager = SandboxManager()
        count = manager.cleanup_unhealthy()
        assert count == 0


class TestSandboxManagerWithDocker:
    """测试沙箱管理器（需要 Docker）"""

    @pytest.fixture
    def mock_docker_client(self) -> Mock:
        """创建 Mock Docker 客户端"""
        mock_client = MagicMock()
        mock_client.ping.return_value = True

        mock_container = MagicMock()
        mock_container.id = "test-container-id"
        mock_container.exec_run.return_value = (0, (b"output", b""))

        mock_client.containers.create.return_value = mock_container
        mock_client.containers.get.return_value = mock_container

        return mock_client

    def test_initialize_success(self, mock_docker_client: Mock) -> None:
        """测试初始化成功"""
        with patch("docker.from_env", return_value=mock_docker_client):
            manager = SandboxManager()
            result = manager.initialize()
            assert result is True
            assert manager._initialized is True

    def test_initialize_failure(self) -> None:
        """测试初始化失败"""
        with patch("docker.from_env", side_effect=Exception("Docker not available")):
            manager = SandboxManager()
            result = manager.initialize()
            assert result is False
            assert manager._initialized is False

    def test_execute_code_not_initialized(self) -> None:
        """测试未初始化时执行代码"""
        manager = SandboxManager()
        manager._initialized = False
        with patch.object(manager, "initialize", return_value=False):
            result = manager.execute_code("print('hello')")
            assert result.success is False
            assert "未初始化" in result.error

    def test_execute_code_success(self, mock_docker_client: Mock) -> None:
        """测试成功执行代码"""
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, (b"hello\n", b""))
        mock_container.id = "test-id"

        mock_docker_client.containers.create.return_value = mock_container
        mock_docker_client.containers.list.return_value = []

        with patch("docker.from_env", return_value=mock_docker_client):
            manager = SandboxManager()
            manager.initialize()
            result = manager.execute_code("print('hello')")
            assert result.success is True
            assert "hello" in result.output


class TestGetSandboxManager:
    """测试获取沙箱管理器单例"""

    def test_singleton(self) -> None:
        """测试单例模式"""
        import backend.sandbox.manager as manager_module

        manager_module._sandbox_manager = None

        manager1 = get_sandbox_manager()
        manager2 = get_sandbox_manager()
        assert manager1 is manager2

        manager_module._sandbox_manager = None


class TestContainerStatus:
    """测试容器状态枚举"""

    def test_status_values(self) -> None:
        """测试状态值"""
        assert ContainerStatus.CREATING.value == "creating"
        assert ContainerStatus.RUNNING.value == "running"
        assert ContainerStatus.IDLE.value == "idle"
        assert ContainerStatus.STOPPED.value == "stopped"
        assert ContainerStatus.ERROR.value == "error"
