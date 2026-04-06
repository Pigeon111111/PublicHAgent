"""FastAPI 应用主模块

提供 FastAPI 应用实例、CORS 配置、中间件和路由注册。
"""

import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes import config, files, history
from backend.api.websocket import router as websocket_router

logger = logging.getLogger(__name__)


class APIError(Exception):
    """API 错误基类"""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class AppSettings:
    """应用配置"""

    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        config_path = Path(__file__).parent.parent / "config" / "settings.json"
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                self._config = json.load(f)

    @property
    def app_name(self) -> str:
        return str(self._config.get("app", {}).get("name", "PubHAgent"))

    @property
    def app_version(self) -> str:
        return str(self._config.get("app", {}).get("version", "0.1.0"))

    @property
    def debug(self) -> bool:
        return bool(self._config.get("app", {}).get("debug", False))

    @property
    def cors_origins(self) -> list[str]:
        origins = self._config.get("api", {}).get("cors_origins", ["http://localhost:3000"])
        return list(origins) if isinstance(origins, list) else ["http://localhost:3000"]

    @property
    def api_host(self) -> str:
        return str(self._config.get("api", {}).get("host", "0.0.0.0"))

    @property
    def api_port(self) -> int:
        return int(self._config.get("api", {}).get("port", 8000))

    @property
    def websocket_path(self) -> str:
        return str(self._config.get("api", {}).get("websocket_path", "/ws"))

    @property
    def max_iterations(self) -> int:
        return int(self._config.get("agent", {}).get("max_iterations", 10))

    @property
    def reflection_attempts(self) -> int:
        return int(self._config.get("agent", {}).get("reflection_attempts", 3))

    @property
    def sandbox_enabled(self) -> bool:
        return bool(self._config.get("sandbox", {}).get("enabled", True))

    @property
    def sandbox_timeout(self) -> int:
        return int(self._config.get("sandbox", {}).get("timeout", 60))


_settings: AppSettings | None = None


def get_settings() -> AppSettings:
    """获取应用配置单例"""
    global _settings
    if _settings is None:
        _settings = AppSettings()
    return _settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """应用生命周期管理"""
    settings = get_settings()
    logger.info(f"启动 {settings.app_name} v{settings.app_version}")

    data_dir = Path("data/uploads")
    data_dir.mkdir(parents=True, exist_ok=True)

    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    yield

    logger.info("关闭应用")


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="公共卫生数据分析智能体系统 API",
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next: Any) -> Any:
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(
            f"{request.method} {request.url.path} - "
            f"{response.status_code} - {process_time:.3f}s"
        )
        return response

    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(f"未处理的异常: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "内部服务器错误",
                "details": {"type": type(exc).__name__},
            },
        )

    app.include_router(websocket_router, prefix="/ws", tags=["websocket"])
    app.include_router(files.router, prefix="/api", tags=["files"])
    app.include_router(history.router, prefix="/api", tags=["history"])
    app.include_router(config.router, prefix="/api", tags=["config"])

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "healthy", "version": settings.app_version}

    @app.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
        }

    uploads_dir = Path("data/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

    return app


app = create_app()
