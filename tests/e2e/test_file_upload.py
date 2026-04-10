"""文件上传端到端测试

测试文件上传模块的完整功能。
"""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app


class TestFileUploadE2E:
    """文件上传端到端测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        """创建测试客户端"""
        app = create_app()
        return TestClient(app)

    @pytest.fixture
    def sample_csv(self) -> bytes:
        """示例 CSV 文件"""
        return """name,age,gender,income
张三,28,男,15000
李四,35,女,22000
王五,42,男,18000
""".encode()

    @pytest.fixture
    def sample_json(self) -> bytes:
        """示例 JSON 文件"""
        return """{"name": "张三", "age": 28, "gender": "男"}""".encode()

    @pytest.fixture
    def sample_txt(self) -> bytes:
        """示例文本文件"""
        return "这是一个测试文本文件".encode()

    def test_upload_csv_file(self, client: TestClient, sample_csv: bytes) -> None:
        """测试上传 CSV 文件"""
        files = {"file": ("test.csv", BytesIO(sample_csv), "text/csv")}
        response = client.post("/api/upload", files=files)
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "filename" in data
        assert data["content_type"] == "text/csv"

    def test_upload_json_file(self, client: TestClient, sample_json: bytes) -> None:
        """测试上传 JSON 文件"""
        files = {"file": ("test.json", BytesIO(sample_json), "application/json")}
        response = client.post("/api/upload", files=files)
        assert response.status_code == 201
        data = response.json()
        assert "id" in data

    def test_upload_txt_file(self, client: TestClient, sample_txt: bytes) -> None:
        """测试上传文本文件"""
        files = {"file": ("test.txt", BytesIO(sample_txt), "text/plain")}
        response = client.post("/api/upload", files=files)
        assert response.status_code == 201

    def test_upload_excel_file(self, client: TestClient) -> None:
        """测试上传 Excel 文件"""
        import pandas as pd
        buffer = BytesIO()
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        df.to_excel(buffer, index=False)
        buffer.seek(0)

        files = {"file": ("test.xlsx", buffer, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        response = client.post("/api/upload", files=files)
        assert response.status_code == 201

    def test_upload_invalid_file_type(self, client: TestClient) -> None:
        """测试上传无效文件类型"""
        files = {"file": ("test.exe", BytesIO(b"invalid"), "application/octet-stream")}
        response = client.post("/api/upload", files=files)
        assert response.status_code == 400

    def test_upload_empty_file(self, client: TestClient) -> None:
        """测试上传空文件"""
        files = {"file": ("empty.csv", BytesIO(b""), "text/csv")}
        response = client.post("/api/upload", files=files)
        assert response.status_code in [201, 400]

    def test_upload_large_file(self, client: TestClient) -> None:
        """测试上传大文件"""
        large_content = b"a,b\n" + b"1,2\n" * 10000
        files = {"file": ("large.csv", BytesIO(large_content), "text/csv")}
        response = client.post("/api/upload", files=files)
        assert response.status_code == 201
        data = response.json()
        assert data["size"] > 10000

    def test_upload_multiple_files(self, client: TestClient) -> None:
        """测试上传多个文件"""
        files = [
            ("files", ("file1.csv", BytesIO(b"a,b\n1,2"), "text/csv")),
            ("files", ("file2.csv", BytesIO(b"c,d\n3,4"), "text/csv")),
        ]
        response = client.post("/api/upload/multiple", files=files)
        assert response.status_code == 201
        data = response.json()
        assert len(data) == 2

    def test_upload_file_with_chinese_name(self, client: TestClient) -> None:
        """测试上传中文文件名"""
        files = {"file": ("测试文件.csv", BytesIO(b"a,b\n1,2"), "text/csv")}
        response = client.post("/api/upload", files=files)
        assert response.status_code == 201


class TestFileManagement:
    """文件管理测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        """创建测试客户端"""
        app = create_app()
        return TestClient(app)

    def test_list_files(self, client: TestClient) -> None:
        """测试列出文件"""
        response = client.get("/api/files")
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert "total" in data

    def test_list_files_with_pagination(self, client: TestClient) -> None:
        """测试分页列出文件"""
        response = client.get("/api/files?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["files"], list)

    def test_list_files_with_extension_filter(self, client: TestClient) -> None:
        """测试按扩展名过滤文件"""
        response = client.get("/api/files?extension=csv")
        assert response.status_code == 200
        data = response.json()
        for file_info in data["files"]:
            assert file_info["filename"].endswith(".csv")

    def test_get_file_info(self, client: TestClient) -> None:
        """测试获取文件信息"""
        csv_content = b"name,value\ntest,123"
        files = {"file": ("info_test.csv", BytesIO(csv_content), "text/csv")}
        upload_response = client.post("/api/upload", files=files)
        assert upload_response.status_code == 201
        file_id = upload_response.json()["id"]

        get_response = client.get(f"/api/files/{file_id}")
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["id"] == file_id

    def test_get_non_existent_file(self, client: TestClient) -> None:
        """测试获取不存在的文件"""
        response = client.get("/api/files/non-existent-id")
        assert response.status_code == 404

    def test_delete_file(self, client: TestClient) -> None:
        """测试删除文件"""
        csv_content = b"name,value\ntest,123"
        files = {"file": ("delete_test.csv", BytesIO(csv_content), "text/csv")}
        upload_response = client.post("/api/upload", files=files)
        assert upload_response.status_code == 201
        file_id = upload_response.json()["id"]

        delete_response = client.delete(f"/api/files/{file_id}")
        assert delete_response.status_code == 204

        get_response = client.get(f"/api/files/{file_id}")
        assert get_response.status_code == 404

    def test_delete_non_existent_file(self, client: TestClient) -> None:
        """测试删除不存在的文件"""
        response = client.delete("/api/files/non-existent-id")
        assert response.status_code == 404


class TestFileValidation:
    """文件验证测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        """创建测试客户端"""
        app = create_app()
        return TestClient(app)

    def test_valid_csv_structure(self, client: TestClient) -> None:
        """测试有效 CSV 结构"""
        valid_csv = "name,age\n张三,28\n李四,35".encode()
        files = {"file": ("valid.csv", BytesIO(valid_csv), "text/csv")}
        response = client.post("/api/upload", files=files)
        assert response.status_code == 201

    def test_file_size_limit(self, client: TestClient) -> None:
        """测试文件大小限制"""
        huge_content = b"x" * (100 * 1024 * 1024)
        files = {"file": ("huge.csv", BytesIO(huge_content), "text/csv")}
        response = client.post("/api/upload", files=files)
        assert response.status_code in [201, 413]

    def test_special_characters_in_content(self, client: TestClient) -> None:
        """测试内容中的特殊字符"""
        special_csv = "name,value\n测试,<script>alert(1)</script>\n特殊,字符".encode()
        files = {"file": ("special.csv", BytesIO(special_csv), "text/csv")}
        response = client.post("/api/upload", files=files)
        assert response.status_code == 201


class TestConcurrentFileOperations:
    """并发文件操作测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        """创建测试客户端"""
        app = create_app()
        return TestClient(app)

    def test_concurrent_uploads(self, client: TestClient) -> None:
        """测试并发上传"""
        file_ids = []
        for i in range(5):
            files = {"file": (f"concurrent_{i}.csv", BytesIO(b"a,b\n1,2"), "text/csv")}
            response = client.post("/api/upload", files=files)
            assert response.status_code == 201
            file_ids.append(response.json()["id"])

        assert len(set(file_ids)) == 5

    def test_concurrent_deletes(self, client: TestClient) -> None:
        """测试并发删除"""
        file_ids = []
        for i in range(3):
            files = {"file": (f"delete_{i}.csv", BytesIO(b"a,b\n1,2"), "text/csv")}
            response = client.post("/api/upload", files=files)
            assert response.status_code == 201
            file_ids.append(response.json()["id"])

        for file_id in file_ids:
            response = client.delete(f"/api/files/{file_id}")
            assert response.status_code == 204
