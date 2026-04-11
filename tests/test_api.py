"""API 模块测试

测试 FastAPI 应用、WebSocket、REST API 和流式输出协议。
"""

import json
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.main import APIError, AppSettings, create_app
from backend.api.protocol import (
    MessageFactory,
    MessageType,
    ProgressTracker,
    UserMessage,
    deserialize_message,
    serialize_message,
)
from backend.api.websocket import ConnectionManager, SessionContext


class TestAppSettings:
    """测试应用配置"""

    def test_default_settings(self) -> None:
        """测试默认配置"""
        settings = AppSettings()
        assert settings.app_name == "PubHAgent"
        assert settings.app_version == "0.1.0"
        assert settings.debug is False
        assert "http://localhost:3000" in settings.cors_origins

    def test_api_settings(self) -> None:
        """测试 API 配置"""
        settings = AppSettings()
        assert settings.api_host == "0.0.0.0"
        assert settings.api_port == 8000
        assert settings.websocket_path == "/ws"


class TestAPIError:
    """测试 API 错误"""

    def test_api_error_creation(self) -> None:
        """测试创建 API 错误"""
        error = APIError(
            message="测试错误",
            status_code=400,
            details={"key": "value"},
        )
        assert error.message == "测试错误"
        assert error.status_code == 400
        assert error.details == {"key": "value"}


class TestMessageProtocol:
    """测试消息协议"""

    def test_user_message_creation(self) -> None:
        """测试创建用户消息"""
        message = MessageFactory.create_user_message(
            session_id="test-session",
            content="分析这组数据",
            user_id="user1",
        )
        assert message.type == MessageType.USER
        assert message.session_id == "test-session"
        assert message.content == "分析这组数据"
        assert message.user_id == "user1"

    def test_agent_message_creation(self) -> None:
        """测试创建 Agent 消息"""
        message = MessageFactory.create_agent_message(
            session_id="test-session",
            content="分析结果",
            intent="descriptive_analysis",
            is_streaming=True,
        )
        assert message.type == MessageType.AGENT
        assert message.content == "分析结果"
        assert message.intent == "descriptive_analysis"
        assert message.is_streaming is True

    def test_status_message_creation(self) -> None:
        """测试创建状态消息"""
        message = MessageFactory.create_status(
            session_id="test-session",
            status="processing",
            message="正在处理",
        )
        assert message.type == MessageType.STATUS
        assert message.status == "processing"
        assert message.message == "正在处理"

    def test_progress_message_creation(self) -> None:
        """测试创建进度消息"""
        message = MessageFactory.create_progress(
            session_id="test-session",
            stage="intent",
            progress=50,
            message="识别意图中",
        )
        assert message.type == MessageType.PROGRESS
        assert message.stage == "intent"
        assert message.progress == 50

    def test_error_message_creation(self) -> None:
        """测试创建错误消息"""
        message = MessageFactory.create_error(
            session_id="test-session",
            error_code="TEST_ERROR",
            error_message="测试错误",
        )
        assert message.type == MessageType.ERROR
        assert message.error_code == "TEST_ERROR"
        assert message.error_message == "测试错误"

    def test_message_serialization(self) -> None:
        """测试消息序列化"""
        message = UserMessage(
            session_id="test-session",
            content="测试内容",
        )
        json_str = serialize_message(message)
        assert isinstance(json_str, str)

        data = json.loads(json_str)
        assert data["type"] == "user"
        assert data["session_id"] == "test-session"
        assert data["content"] == "测试内容"

    def test_message_deserialization(self) -> None:
        """测试消息反序列化"""
        json_str = json.dumps({
            "type": "user",
            "session_id": "test-session",
            "content": "测试内容",
            "user_id": "default",
            "context": {},
        })

        message = deserialize_message(json_str)
        assert isinstance(message, UserMessage)
        assert message.content == "测试内容"


class TestProgressTracker:
    """测试进度追踪器"""

    def test_start_stage(self) -> None:
        """测试开始阶段"""
        tracker = ProgressTracker("test-session")
        message = tracker.start_stage("intent", "开始识别意图")

        assert tracker._current_stage == "intent"
        assert tracker._current_progress == 0
        assert message.stage == "intent"
        assert message.progress == 0

    def test_update_progress(self) -> None:
        """测试更新进度"""
        tracker = ProgressTracker("test-session")
        tracker.start_stage("planning")

        message = tracker.update_progress(50, "规划中")
        assert tracker._current_progress == 50
        assert message.progress == 50

    def test_complete_stage(self) -> None:
        """测试完成阶段"""
        tracker = ProgressTracker("test-session")
        tracker.start_stage("execution")

        message = tracker.complete_stage("执行完成")
        assert tracker._current_progress == 100
        assert message.progress == 100

    def test_progress_bounds(self) -> None:
        """测试进度边界"""
        tracker = ProgressTracker("test-session")
        tracker.start_stage("test")

        tracker.update_progress(150)
        assert tracker._current_progress == 100

        tracker.update_progress(-10)
        assert tracker._current_progress == 0

    def test_get_summary(self) -> None:
        """测试获取摘要"""
        tracker = ProgressTracker("test-session")
        tracker.start_stage("stage1")
        tracker.update_progress(50)
        tracker.complete_stage()

        summary = tracker.get_summary()
        assert summary["session_id"] == "test-session"
        assert summary["current_stage"] == "stage1"
        assert summary["current_progress"] == 100
        assert len(summary["stages"]) == 1


class TestConnectionManager:
    """测试 WebSocket 连接管理器"""

    def test_connection_manager_init(self) -> None:
        """测试初始化"""
        manager = ConnectionManager()
        assert len(manager._active_connections) == 0
        assert len(manager._session_data) == 0

    def test_is_connected(self) -> None:
        """测试连接检查"""
        manager = ConnectionManager()
        assert manager.is_connected("non-existent") is False

    def test_get_session_ids(self) -> None:
        """测试获取会话 ID"""
        manager = ConnectionManager()
        assert manager.get_session_ids() == []

    def test_disconnect_non_existent(self) -> None:
        """测试断开不存在的连接"""
        manager = ConnectionManager()
        manager.disconnect("non-existent")


class TestSessionContext:
    """测试会话上下文"""

    def test_session_context_creation(self) -> None:
        """测试创建会话上下文"""
        context = SessionContext("test-session", "user1")
        assert context.session_id == "test-session"
        assert context.user_id == "user1"
        assert context.workflow is None
        assert context.is_interrupted() is False

    def test_interrupt(self) -> None:
        """测试中断"""
        context = SessionContext("test-session")
        context.interrupt()
        assert context.is_interrupted() is True

    def test_reset(self) -> None:
        """测试重置"""
        context = SessionContext("test-session")
        context.interrupt()
        context.reset()
        assert context.is_interrupted() is False


class TestFastAPIApp:
    """测试 FastAPI 应用"""

    @pytest.fixture
    def client(self) -> TestClient:
        """创建测试客户端"""
        app = create_app()
        return TestClient(app)

    def test_health_check(self, client: TestClient) -> None:
        """测试健康检查"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_root_endpoint(self, client: TestClient) -> None:
        """测试根路径"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data

    def test_openapi_docs(self, client: TestClient) -> None:
        """测试 API 文档"""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_cors_headers(self, client: TestClient) -> None:
        """测试 CORS 头"""
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.status_code == 200


class TestFileRoutes:
    """测试文件路由"""

    def test_list_files_empty(self, tmp_path: Path) -> None:
        """测试空文件列表"""
        empty_dir = tmp_path / "uploads"
        empty_dir.mkdir()

        from backend.api.deps import get_upload_dir
        from backend.api.main import create_app

        app = create_app()
        app.dependency_overrides[get_upload_dir] = lambda: empty_dir

        client = TestClient(app)
        response = client.get("/api/files")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["files"] == []

    def test_upload_invalid_file_type(self) -> None:
        """测试上传无效文件类型"""
        app = create_app()
        client = TestClient(app)
        file_content = b"test content"
        files = {"file": ("test.exe", BytesIO(file_content), "application/octet-stream")}

        response = client.post("/api/upload", files=files)
        assert response.status_code == 400


class TestHistoryRoutes:
    """测试历史记录路由"""

    @pytest.fixture
    def client(self) -> TestClient:
        """创建测试客户端"""
        app = create_app()
        return TestClient(app)

    def test_list_conversations_empty(self, client: TestClient) -> None:
        """测试空对话列表"""
        from backend.api.routes.history import reset_history_storage
        reset_history_storage()

        response = client.get("/api/conversations")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    def test_create_conversation(self, client: TestClient) -> None:
        """测试创建对话"""
        from backend.api.routes.history import reset_history_storage
        reset_history_storage()

        response = client.post("/api/conversations?title=测试对话")
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "测试对话"
        assert data["message_count"] == 0

    def test_get_non_existent_conversation(self, client: TestClient) -> None:
        """测试获取不存在的对话"""
        response = client.get("/api/conversations/non-existent")
        assert response.status_code == 404


class TestExtendedHistoryRoutes:
    """测试扩展历史与方法接口。"""

    @pytest.fixture
    def client(self) -> TestClient:
        app = create_app()
        return TestClient(app)

    def test_analysis_detail_and_evaluation_review(self, client: TestClient) -> None:
        """测试分析详情、评估查询和审阅接口。"""
        from backend.api.routes.history import reset_history_storage
        from backend.storage.history_storage import get_history_storage

        reset_history_storage()
        storage = get_history_storage()
        record = storage.create_analysis_record(
            query="测试回归分析",
            intent="regression_analysis",
            status="completed",
            result_summary="已完成",
            steps_count=1,
            task_family="regression_analysis",
            evaluation_score=0.91,
            evaluation_passed=True,
            evaluation_summary="通过",
        )
        storage.upsert_evaluation_report(
            analysis_record_id=record["id"],
            session_id="session_api_test",
            trajectory_id="traj_api_test",
            task_family="regression_analysis",
            final_score=0.91,
            passed=True,
            summary="评估通过",
            report_json={
                "task_family": "regression_analysis",
                "passed": True,
                "final_score": 0.91,
                "summary": "评估通过",
                "score_breakdown": {
                    "artifact_score": 1.0,
                    "statistical_score": 0.9,
                    "process_score": 0.85,
                    "report_score": 0.9,
                },
            },
            associated_skill="learned_regression_variant",
        )

        detail_response = client.get(f"/api/analysis/{record['id']}")
        assert detail_response.status_code == 200
        detail_data = detail_response.json()
        assert detail_data["record"]["task_family"] == "regression_analysis"
        assert detail_data["evaluation"]["summary"] == "评估通过"

        evaluation_response = client.get(f"/api/analysis/{record['id']}/evaluation")
        assert evaluation_response.status_code == 200
        assert evaluation_response.json()["associated_skill"] == "learned_regression_variant"

        review_response = client.post(
            f"/api/analysis/{record['id']}/evaluation/review",
            json={
                "review_status": "confirmed",
                "review_label": "correct",
                "review_comment": "结果核对无误",
                "reviewed_by": "tester",
            },
        )
        assert review_response.status_code == 200
        assert review_response.json()["review_status"] == "confirmed"

        rerun_response = client.post(f"/api/analysis/{record['id']}/rerun")
        assert rerun_response.status_code == 200
        rerun_data = rerun_response.json()
        assert rerun_data["analysis_id"] == record["id"]
        assert rerun_data["query"] == "测试回归分析"

    def test_method_family_and_preference_routes(self, client: TestClient) -> None:
        """测试方法家族列表、变体列表与偏好设置。"""
        from backend.api.routes.history import reset_history_storage
        from backend.learning.skill_learning import SkillLearningService
        from backend.tools.skills.registry import reset_skill_registry

        reset_history_storage()
        reset_skill_registry()
        SkillLearningService().migrate_legacy_skills()

        families_response = client.get("/api/method-families")
        assert families_response.status_code == 200
        families = families_response.json()["families"]
        assert any(item["family"] == "regression_analysis" for item in families)

        variants_response = client.get("/api/method-families/regression_analysis/variants")
        assert variants_response.status_code == 200
        variants = variants_response.json()["variants"]
        assert isinstance(variants, list)

        preferred_variant = variants[0]["name"] if variants else ""
        preference_response = client.post(
            "/api/method-families/regression_analysis/preferred-variant",
            json={"preferred_variant": preferred_variant, "user_id": "default"},
        )
        assert preference_response.status_code == 200
        assert preference_response.json()["preference"]["preferred_variant"] == preferred_variant


class TestConfigRoutes:
    """测试配置路由"""

    @pytest.fixture
    def client(self) -> TestClient:
        """创建测试客户端"""
        app = create_app()
        return TestClient(app)

    def test_get_config(self, client: TestClient) -> None:
        """测试获取配置"""
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "app" in data
        assert "agent" in data
        assert "sandbox" in data

    def test_get_agent_config(self, client: TestClient) -> None:
        """测试获取 Agent 配置"""
        response = client.get("/api/config/agent")
        assert response.status_code == 200
        data = response.json()
        assert "max_iterations" in data
        assert "reflection_attempts" in data

    def test_get_sandbox_config(self, client: TestClient) -> None:
        """测试获取沙箱配置"""
        response = client.get("/api/config/sandbox")
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "timeout" in data
