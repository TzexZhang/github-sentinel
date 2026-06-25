"""本地开发启动器。

直接启动 uvicorn,改完代码后手动停止(Ctrl+C)再重新运行。
不使用 --reload:uvicorn 的热重载在 Windows 上会卡死在
``Waiting for connections to close``,手动重启最简单可靠。

用法:
    uv run python scripts/dev.py                  # 默认 127.0.0.1:8000
    uv run python scripts/dev.py --port 8001
"""

from __future__ import annotations

import argparse
import subprocess
import sys

# uvicorn 应用工厂入口:create_app() 返回 FastAPI 实例
APP_TARGET = "app.main:create_app"
# 优雅关闭超时（秒）：Ctrl+C 后最多等待这么久，超时则强制关闭残留连接。
# 不设置时默认 None 会无限等待——浏览器开着 dashboard 的 Gradio 长连接时，
# 会永久卡在 "Waiting for connections to close"。连按两次 Ctrl+C 可立即强退。
GRACEFUL_SHUTDOWN_SECONDS = 3


def main() -> None:
    parser = argparse.ArgumentParser(
        description="启动开发服务器(直接运行 uvicorn,改代码后手动重启)。",
    )
    parser.add_argument("--host", default="127.0.0.1", help="监听地址,默认 127.0.0.1")
    parser.add_argument("--port", type=int, default=8000, help="监听端口,默认 8000")
    args = parser.parse_args()

    # 用当前解释器直接启动 uvicorn,避免依赖 uv 包装
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        APP_TARGET,
        "--factory",
        "--host",
        args.host,
        "--port",
        str(args.port),
        # 限制优雅关闭等待时间，避免 Ctrl+C 后卡死
        "--timeout-graceful-shutdown",
        str(GRACEFUL_SHUTDOWN_SECONDS),
    ]
    try:
        subprocess.run(command, check=False)
    except KeyboardInterrupt:
        # Ctrl+C 由 uvicorn 自身处理,这里仅吞掉可能向上冒泡的键盘中断
        sys.exit(0)


if __name__ == "__main__":
    main()
