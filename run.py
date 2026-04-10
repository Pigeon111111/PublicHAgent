#!/usr/bin/env python
"""PubHAgent 统一启动脚本

提供简单统一的入口来启动后端服务和前端服务。
"""

import argparse
import importlib.util
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent


def check_python_version() -> bool:
    """检查 Python 版本"""
    if sys.version_info < (3, 10):  # noqa: UP036
        print("错误: 需要 Python 3.10 或更高版本")
        return False
    return True


def check_dependencies() -> bool:
    """检查依赖是否安装"""
    missing = [
        module_name
        for module_name in ("fastapi", "uvicorn")
        if importlib.util.find_spec(module_name) is None
    ]

    if not missing:
        print("✓ 后端依赖已安装")
        return True

    print(f"错误: 缺少依赖 - {', '.join(missing)}")
    print("请运行: pip install -r requirements.txt")
    return False


def check_config() -> bool:
    """检查配置文件"""
    config_dir = PROJECT_ROOT / "backend" / "config"
    required_files = [
        "settings.json",
        "models.json",
    ]

    for file in required_files:
        if not (config_dir / file).exists():
            print(f"警告: 配置文件 {file} 不存在")

    return True


def start_backend(blocking: bool = False) -> subprocess.Popen | None:
    """启动后端服务"""
    print("正在启动后端服务...")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.api.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--reload",
            ],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        if not blocking:
            import threading

            def print_output():
                for line in process.stdout:
                    print(f"[后端] {line.rstrip()}")

            thread = threading.Thread(target=print_output, daemon=True)
            thread.start()

        print("✓ 后端服务已启动: http://localhost:8000")
        return process
    except Exception as e:
        print(f"错误: 启动后端服务失败 - {e}")
        return None


def start_frontend() -> subprocess.Popen | None:
    """启动前端服务"""
    print("正在启动前端服务...")

    frontend_dir = PROJECT_ROOT / "frontend"

    if not frontend_dir.exists():
        print("错误: 前端目录不存在")
        return None

    try:
        npm_cmd = "npm" if os.name != "nt" else "npm.cmd"

        process = subprocess.Popen(
            [npm_cmd, "run", "dev"],
            cwd=frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        import threading

        def print_output():
            for line in process.stdout:
                print(f"[前端] {line.rstrip()}")

        thread = threading.Thread(target=print_output, daemon=True)
        thread.start()

        print("✓ 前端服务已启动")
        return process
    except Exception as e:
        print(f"错误: 启动前端服务失败 - {e}")
        return None


def open_browser() -> None:
    """打开浏览器"""
    time.sleep(2)
    webbrowser.open("http://localhost:5173")


def wait_for_services(backend_process: subprocess.Popen, frontend_process: subprocess.Popen) -> None:
    """等待服务进程"""
    try:
        backend_process.wait()
    except KeyboardInterrupt:
        print("\n正在关闭服务...")
        if backend_process:
            backend_process.terminate()
        if frontend_process:
            frontend_process.terminate()
        print("服务已关闭")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="PubHAgent 统一启动脚本")
    parser.add_argument("--dev", action="store_true", help="开发模式启动（默认）")
    parser.add_argument("--prod", action="store_true", help="生产模式启动")
    parser.add_argument("--backend-only", action="store_true", help="仅启动后端服务")
    parser.add_argument("--frontend-only", action="store_true", help="仅启动前端服务")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")

    args = parser.parse_args()

    print("=" * 50)
    print("PubHAgent 启动器")
    print("=" * 50)

    if not check_python_version():
        sys.exit(1)

    if not check_dependencies():
        sys.exit(1)

    check_config()

    backend_process = None
    frontend_process = None

    try:
        if args.frontend_only:
            frontend_process = start_frontend()
        elif args.backend_only:
            backend_process = start_backend(blocking=True)
        else:
            backend_process = start_backend()
            frontend_process = start_frontend()

            if not args.no_browser:
                open_browser()

        if backend_process or frontend_process:
            print("\n" + "=" * 50)
            print("服务已启动，按 Ctrl+C 停止")
            print("=" * 50)

            if backend_process and frontend_process:
                wait_for_services(backend_process, frontend_process)
            elif backend_process:
                backend_process.wait()
            elif frontend_process:
                frontend_process.wait()

    except KeyboardInterrupt:
        print("\n正在关闭服务...")
    finally:
        if backend_process:
            backend_process.terminate()
        if frontend_process:
            frontend_process.terminate()
        print("服务已关闭")


if __name__ == "__main__":
    main()
