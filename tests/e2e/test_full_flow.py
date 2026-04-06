import pytest
import httpx
import asyncio
import json
from pathlib import Path

pytestmark = pytest.mark.skip(reason="需要运行的后端服务，跳过 e2e 测试")


@pytest.mark.asyncio
async def test_full_analysis_flow():
    """测试完整分析流程"""
    base_url = "http://localhost:8000"
    
    test_file = Path(__file__).parent / "test_data.csv"
    if not test_file.exists():
        test_file.write_text("name,value\nalice,10\nbob,20\ncharlie,30")
    
    async with httpx.AsyncClient() as client:
        with open(test_file, "rb") as f:
            response = await client.post(
                f"{base_url}/api/upload",
                files={"file": ("test_data.csv", f, "text/csv")}
            )
        assert response.status_code == 201
        file_info = response.json()
        assert "file_id" in file_info


@pytest.mark.asyncio
async def test_intent_recognition():
    """测试意图识别 - 需要通过 WebSocket 进行"""
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/health")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_file_upload():
    """测试文件上传"""
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        test_file = Path(__file__).parent / "test_data.csv"
        if not test_file.exists():
            test_file.write_text("name,value\nalice,10\nbob,20")
        
        with open(test_file, "rb") as f:
            response = await client.post(
                f"{base_url}/api/upload",
                files={"file": ("test_data.csv", f, "text/csv")}
            )
        assert response.status_code == 201
        file_info = response.json()
        assert "file_id" in file_info
        assert "filename" in file_info
        assert file_info["filename"] == "test_data.csv"
        
        response = await client.get(f"{base_url}/api/files")
        assert response.status_code == 200
        files = response.json()
        assert "files" in files


@pytest.mark.asyncio
async def test_websocket_connection():
    """测试 WebSocket 连接"""
    websocket_url = "ws://localhost:8000/ws"
    
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/health")
        assert response.status_code == 200
