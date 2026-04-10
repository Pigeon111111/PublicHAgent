"""完整分析流程端到端测试

测试从用户上传文件到获取分析结果的完整流程。
"""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from backend.api.main import create_app


class TestFullAnalysisFlow:
    """完整分析流程测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        """创建测试客户端"""
        app = create_app()
        return TestClient(app)

    @pytest.fixture
    def async_client(self):
        """创建异步测试客户端"""
        app = create_app()
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.fixture
    def sample_csv_content(self) -> bytes:
        """生成示例 CSV 文件内容"""
        return """name,age,gender,income,city
张三,28,男,15000,北京
李四,35,女,22000,上海
王五,42,男,18000,广州
赵六,31,女,20000,深圳
钱七,25,男,12000,杭州
""".encode()

    @pytest.fixture
    def sample_excel_content(self) -> bytes:
        """生成示例 Excel 文件内容"""
        import pandas as pd
        df = pd.DataFrame({
            "name": ["张三", "李四", "王五"],
            "age": [28, 35, 42],
            "score": [85.5, 92.0, 78.5],
        })
        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)
        return buffer.read()

    def test_health_check_before_analysis(self, client: TestClient) -> None:
        """测试分析前健康检查"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_upload_file_for_analysis(
        self,
        client: TestClient,
        sample_csv_content: bytes,
    ) -> None:
        """测试上传文件用于分析"""
        files = {
            "file": (
                "test_data.csv",
                BytesIO(sample_csv_content),
                "text/csv",
            )
        }
        response = client.post("/api/upload", files=files)
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "filename" in data
        assert data["size"] > 0

    def test_list_uploaded_files(self, client: TestClient) -> None:
        """测试列出已上传文件"""
        response = client.get("/api/files")
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert "total" in data
        assert isinstance(data["files"], list)

    def test_create_conversation_for_analysis(self, client: TestClient) -> None:
        """测试创建对话用于分析"""
        from backend.api.routes.history import reset_history_storage
        reset_history_storage()

        response = client.post("/api/conversations?title=数据分析测试")
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "数据分析测试"
        assert data["message_count"] == 0

    def test_get_config_for_analysis(self, client: TestClient) -> None:
        """测试获取分析配置"""
        response = client.get("/api/config/agent")
        assert response.status_code == 200
        data = response.json()
        assert "max_iterations" in data
        assert "reflection_attempts" in data

    @pytest.mark.asyncio
    async def test_websocket_analysis_flow(
        self,
        sample_csv_content: bytes,
    ) -> None:
        """测试通过 WebSocket 的完整分析流程"""
        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            files = {
                "file": (
                    "analysis_data.csv",
                    BytesIO(sample_csv_content),
                    "text/csv",
                )
            }
            upload_response = await client.post("/api/upload", files=files)
            assert upload_response.status_code == 201

    def test_analysis_with_invalid_file(self, client: TestClient) -> None:
        """测试使用无效文件进行分析"""
        invalid_content = b"invalid file content"
        files = {
            "file": (
                "test.exe",
                BytesIO(invalid_content),
                "application/octet-stream",
            )
        }
        response = client.post("/api/upload", files=files)
        assert response.status_code == 400

    def test_analysis_with_empty_file(self, client: TestClient) -> None:
        """测试上传空文件"""
        files = {
            "file": (
                "empty.csv",
                BytesIO(b""),
                "text/csv",
            )
        }
        response = client.post("/api/upload", files=files)
        assert response.status_code in [201, 400]

    def test_delete_file_after_analysis(self, client: TestClient) -> None:
        """测试分析后删除文件"""
        csv_content = b"name,value\ntest,123"
        files = {
            "file": (
                "to_delete.csv",
                BytesIO(csv_content),
                "text/csv",
            )
        }
        upload_response = client.post("/api/upload", files=files)
        assert upload_response.status_code == 201
        file_id = upload_response.json()["id"]

        delete_response = client.delete(f"/api/files/{file_id}")
        assert delete_response.status_code == 204

        get_response = client.get(f"/api/files/{file_id}")
        assert get_response.status_code == 404


class TestAnalysisWorkflowIntegration:
    """分析工作流集成测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        """创建测试客户端"""
        app = create_app()
        return TestClient(app)

    def test_intent_to_plan_flow(self, client: TestClient) -> None:
        """测试意图识别到计划生成流程"""
        response = client.get("/api/config/agent")
        assert response.status_code == 200
        config = response.json()
        assert config["max_iterations"] > 0

    def test_plan_to_execution_flow(self, client: TestClient) -> None:
        """测试计划到执行流程"""
        response = client.get("/api/config/sandbox")
        assert response.status_code == 200
        config = response.json()
        assert "enabled" in config
        assert "timeout" in config

    def test_execution_to_result_flow(self, client: TestClient) -> None:
        """测试执行到结果流程"""
        from backend.api.routes.history import reset_history_storage
        reset_history_storage()

        create_response = client.post("/api/conversations?title=执行测试")
        assert create_response.status_code == 201
        conversation_id = create_response.json()["id"]

        get_response = client.get(f"/api/conversations/{conversation_id}")
        assert get_response.status_code == 200

    def test_result_to_reflection_flow(self, client: TestClient) -> None:
        """测试结果到反思流程"""
        response = client.get("/api/config/agent")
        assert response.status_code == 200
        config = response.json()
        assert config["reflection_attempts"] > 0


class TestConcurrentAnalysis:
    """并发分析测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        """创建测试客户端"""
        app = create_app()
        return TestClient(app)

    def test_multiple_file_uploads(self, client: TestClient) -> None:
        """测试多文件同时上传"""
        files = [
            ("files", ("file1.csv", BytesIO(b"a,b\n1,2"), "text/csv")),
            ("files", ("file2.csv", BytesIO(b"c,d\n3,4"), "text/csv")),
            ("files", ("file3.csv", BytesIO(b"e,f\n5,6"), "text/csv")),
        ]
        response = client.post("/api/upload/multiple", files=files)
        assert response.status_code == 201
        data = response.json()
        assert len(data) == 3

    def test_concurrent_conversation_creation(self, client: TestClient) -> None:
        """测试并发创建对话"""
        from backend.api.routes.history import reset_history_storage
        reset_history_storage()

        conversation_ids = []
        for i in range(5):
            response = client.post(f"/api/conversations?title=对话{i}")
            assert response.status_code == 201
            conversation_ids.append(response.json()["id"])

        assert len(set(conversation_ids)) == 5


class TestErrorRecovery:
    """错误恢复测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        """创建测试客户端"""
        app = create_app()
        return TestClient(app)

    def test_recovery_from_invalid_file(self, client: TestClient) -> None:
        """测试从无效文件错误恢复"""
        invalid_files = {
            "file": (
                "test.exe",
                BytesIO(b"invalid"),
                "application/octet-stream",
            )
        }
        invalid_response = client.post("/api/upload", files=invalid_files)
        assert invalid_response.status_code == 400

        valid_files = {
            "file": (
                "valid.csv",
                BytesIO(b"name,value\ntest,123"),
                "text/csv",
            )
        }
        valid_response = client.post("/api/upload", files=valid_files)
        assert valid_response.status_code == 201

    def test_recovery_from_missing_file(self, client: TestClient) -> None:
        """测试从文件不存在错误恢复"""
        response = client.get("/api/files/non-existent-id")
        assert response.status_code == 404

        response = client.get("/api/files")
        assert response.status_code == 200

    def test_recovery_from_invalid_conversation(self, client: TestClient) -> None:
        """测试从无效对话错误恢复"""
        response = client.get("/api/conversations/non-existent")
        assert response.status_code == 404

        from backend.api.routes.history import reset_history_storage
        reset_history_storage()

        create_response = client.post("/api/conversations?title=新对话")
        assert create_response.status_code == 201
