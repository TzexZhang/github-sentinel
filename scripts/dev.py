"""本地开发启动器（命令行与 IDE 调试共用同一入口）。

直接在**当前进程**内运行 uvicorn，不用 subprocess 拉子进程——
这样无论命令行运行还是 VSCode 调试（F5），断点都能稳定命中。

用法:
    uv run python scripts/dev.py                  # 默认 127.0.0.1:8000
    uv run python scripts/dev.py --port 8001

调试:
    在 VSCode 中按 F5 选择「调试整个项目」配置，与上面命令运行的是同一个脚本。

注意:
    不使用 --reload：uvicorn 的热重载在 Windows 上会卡死在
    ``Waiting for connections to close``。改完代码手动 Ctrl+C 重启即可。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中。
# 直接运行脚本（python scripts/dev.py 或 VSCode program 方式）时，
# sys.path[0] 是 scripts/ 目录而非项目根，会导致 from app.main import create_app 失败。
# 这里显式插入项目根（scripts 的上一级），保证命令行与调试两种启动方式行为一致。
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import uvicorn  # noqa: E402

# 应用工厂：create_app() 返回 FastAPI 实例。
# 这里直接 import 并实例化，确保 uvicorn 在当前进程运行（断点才能命中）。
from app.main import create_app  # noqa: E402

# Ctrl+C 后最多等待这么久（秒），超时则强制关闭残留连接。
# 不设置时默认 None 会无限等待——浏览器开着 dashboard 的 Gradio 长连接时，
# 会永久卡在 "Waiting for connections to close"。连按两次 Ctrl+C 可立即强退。
GRACEFUL_SHUTDOWN_SECONDS = 3
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def main() -> None:
    parser = argparse.ArgumentParser(
        description="启动开发服务器（命令行与 IDE 调试共用）。",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"监听地址，默认 {DEFAULT_HOST}")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"监听端口，默认 {DEFAULT_PORT}")
    args = parser.parse_args()

    # uvicorn.run 直接在当前进程启动，无需 subprocess。
    # factory=False：我们已传入实例化后的 app 对象，而非工厂字符串。
    uvicorn.run(
        create_app(),
        host=args.host,
        port=args.port,
        timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_SECONDS,
    )


if __name__ == "__main__":
    main()
