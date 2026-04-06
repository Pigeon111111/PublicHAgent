"""WebSocket 连接端到端测试

测试 WebSocket 连接、消息传递和会话管理。
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.api.main import create_app
from backend.api.protocol import (
    AgentMessage,
    ErrorMessage,
    MessageFactory,
    MessageType,
    ProgressMessage,
    StatusMessage,
    UserMessage,
)
from backend.api.websocket import (
    ConnectionManager,
    SessionContext,
    get_or_create_session,
    reset_sessions,
)


class TestWebSocketConnection:
    """WebSocket 连接测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        """创建测试客户端"""
        app = create_app()
        return TestClient(app)

    def test_websocket_connect(self, client: TestClient) -> None:
        """测试 WebSocket 连接"""
        with client.websocket_connect("/ws/test-session-1") as websocket:
            data = websocket.receive_json()
            assert data["type"] == MessageType.STATUS
            assert data["status"] == "connected"

    def test_websocket_disconnect(self, client: TestClient) -> None:
        """测试 WebSocket 断开"""
        with client.websocket_connect("/ws/test-session-2") as websocket:
            websocket.receive_json()
        reset_sessions()

    def test_websocket_ping_pong(self, client: TestClient) -> None:
        """测试心跳消息"""
        with client.websocket_connect("/ws/test-session-3") as websocket:
            websocket.receive_json()
            websocket.send_json({"type": "ping"})
            data = websocket.receive_json()
            assert data["type"] == MessageType.STATUS
            assert data["status"] == "pong"


class TestWebSocketMessaging:
    """WebSocket 消息传递测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        """创建测试客户端"""
        app = create_app()
        return TestClient(app)

    def test_send_user_message(self, client: TestClient) -> None:
        """测试发送用户消息"""
        with client.websocket_connect("/ws/test-session-4") as websocket:
            websocket.receive_json()
            message = {
                "type": MessageType.USER,
                "session_id": "test-session-4",
                "content": "测试消息",
                "user_id": "test-user",
                "context": {},
            }
            websocket.send_json(message)
            response = websocket.receive_json()
            assert response["type"] in [MessageType.STATUS, MessageType.PROGRESS]

    def test_send_invalid_json(self, client: TestClient) -> None:
        """测试发送无效 JSON"""
        with client.websocket_connect("/ws/test-session-5") as websocket:
            websocket.receive_json()
            websocket.send_text("invalid json")
            data = websocket.receive_json()
            assert data["type"] == MessageType.ERROR
            assert data["error_code"] == "INVALID_JSON"

    def test_send_unknown_message_type(self, client: TestClient) -> None:
        """测试发送未知消息类型"""
        with client.websocket_connect("/ws/test-session-6") as websocket:
            websocket.receive_json()
            websocket.send_json({"type": "unknown_type"})
            data = websocket.receive_json()
            assert data["type"] == MessageType.ERROR
            assert data["error_code"] == "UNKNOWN_MESSAGE_TYPE"


class TestWebSocketSession:
    """WebSocket 会话测试"""

    def test_session_context_creation(self) -> None:
        """测试会话上下文创建"""
        context = SessionContext("test-session", "test-user")
        assert context.session_id == "test-session"
        assert context.user_id == "test-user"
        assert context.workflow is None
        assert not context.is_interrupted()

    def test_session_interrupt(self) -> None:
        """测试会话中断"""
        context = SessionContext("test-session")
        context.interrupt()
        assert context.is_interrupted()

    def test_session_reset(self) -> None:
        """测试会话重置"""
        context = SessionContext("test-session")
        context.interrupt()
        context.reset()
        assert not context.is_interrupted()

    def test_get_or_create_session(self) -> None:
        """测试获取或创建会话"""
        reset_sessions()
        context1 = get_or_create_session("session-1", "user-1")
        assert context1.session_id == "session-1"
        assert context1.user_id == "user-1"

        context2 = get_or_create_session("session-1", "user-1")
        assert context2 is context1

    def test_reset_sessions(self) -> None:
        """测试重置会话"""
        get_or_create_session("session-to-reset")
        reset_sessions()
        from backend.api.websocket import sessions
        assert len(sessions) == 0


class TestConnectionManager:
    """连接管理器测试"""

    def test_manager_initialization(self) -> None:
        """测试管理器初始化"""
        manager = ConnectionManager()
        assert len(manager._active_connections) == 0
        assert len(manager._session_data) == 0

    def test_is_connected(self) -> None:
        """测试连接检查"""
        manager = ConnectionManager()
        assert not manager.is_connected("non-existent")

    def test_get_session_ids(self) -> None:
        """测试获取会话 ID 列表"""
        manager = ConnectionManager()
        assert manager.get_session_ids() == []

    def test_disconnect_non_existent(self) -> None:
        """测试断开不存在的连接"""
        manager = ConnectionManager()
        manager.disconnect("non-existent")

    def test_get_session_info(self) -> None:
        """测试获取会话信息"""
        manager = ConnectionManager()
        info = manager.get_session_info("non-existent")
        assert info is None


class TestWebSocketProtocol:
    """WebSocket 协议测试"""

    def test_user_message_creation(self) -> None:
        """测试用户消息创建"""
        message = MessageFactory.create_user_message(
            session_id="test-session",
            content="测试内容",
            user_id="test-user",
        )
        assert message.type == MessageType.USER
        assert message.session_id == "test-session"
        assert message.content == "测试内容"

    def test_agent_message_creation(self) -> None:
        """测试 Agent 消息创建"""
        message = MessageFactory.create_agent_message(
            session_id="test-session",
            content="响应内容",
            intent="test_intent",
        )
        assert message.type == MessageType.AGENT
        assert message.content == "响应内容"

    def test_status_message_creation(self) -> None:
        """测试状态消息创建"""
        message = MessageFactory.create_status(
            session_id="test-session",
            status="processing",
            message="处理中",
        )
        assert message.type == MessageType.STATUS
        assert message.status == "processing"

    def test_progress_message_creation(self) -> None:
        """测试进度消息创建"""
        message = MessageFactory.create_progress(
            session_id="test-session",
            stage="intent",
            progress=50,
            message="识别中",
        )
        assert message.type == MessageType.PROGRESS
        assert message.stage == "intent"
        assert message.progress == 50

    def test_error_message_creation(self) -> None:
        """测试错误消息创建"""
        message = MessageFactory.create_error(
            session_id="test-session",
            error_code="TEST_ERROR",
            error_message="测试错误",
        )
        assert message.type == MessageType.ERROR
        assert message.error_code == "TEST_ERROR"

    def test_message_json_serialization(self) -> None:
        """测试消息 JSON 序列化"""
        message = UserMessage(
            session_id="test-session",
            content="测试内容",
        )
        json_str = message.model_dump_json()
        data = json.loads(json_str)
        assert data["type"] == MessageType.USER
        assert data["session_id"] == "test-session"


class TestWebSocketInterrupt:
    """WebSocket 中断测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        """创建测试客户端"""
        app = create_app()
        return TestClient(app)

    def test_send_interrupt_message(self, client: TestClient) -> None:
        """测试发送中断消息"""
        with client.websocket_connect("/ws/test-session-interrupt") as websocket:
            websocket.receive_json()
            websocket.send_json({"type": MessageType.INTERRUPT})
            data = websocket.receive_json()
            assert data["type"] == MessageType.STATUS
            assert data["status"] == "interrupted"


class TestWebSocketErrorHandling:
    """WebSocket 错误处理测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        """创建测试客户端"""
        app = create_app()
        return TestClient(app)

    def test_malformed_message(self, client: TestClient) -> None:
        """测试格式错误的消息"""
        with client.websocket_connect("/ws/test-session-error") as websocket:
            websocket.receive_json()
            websocket.send_json({"type": MessageType.USER, "invalid_field": "value"})
            data = websocket.receive_json()
            assert data["type"] in [MessageType.STATUS, MessageType.ERROR]

    def test_empty_message(self, client: TestClient) -> None:
        """测试空消息"""
        with client.websocket_connect("/ws/test-session-empty") as websocket:
            websocket.receive_json()
            websocket.send_json({})
            data = websocket.receive_json()
            assert data["type"] == MessageType.ERROR


class TestMultipleWebSocketConnections:
    """多 WebSocket 连接测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        """创建测试客户端"""
        app = create_app()
        return TestClient(app)

    def test_multiple_sessions(self, client: TestClient) -> None:
        """测试多个会话"""
        reset_sessions()

        with client.websocket_connect("/ws/session-1") as ws1:
            ws1.receive_json()
            with client.websocket_connect("/ws/session-2") as ws2:
                ws2.receive_json()

                ws1.send_json({
                    "type": MessageType.USER,
                    "session_id": "session-1",
                    "content": "消息1",
                    "user_id": "user1",
                    "context": {},
                })
                ws2.send_json({
                    "type": MessageType.USER,
                    "session_id": "session-2",
                    "content": "消息2",
                    "user_id": "user2",
                    "context": {},
                })

                response1 = ws1.receive_json()
                response2 = ws2.receive_json()

                assert response1["session_id"] == "session-1"
                assert response2["session_id"] == "session-2"
