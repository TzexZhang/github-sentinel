# --- 标准库导入 ---
# AsyncIterator: 异步迭代器的类型注解，用于标注异步上下文管理器的 yield 返回类型
from collections.abc import AsyncIterator
# asynccontextmanager: 装饰器，将一个异步生成器函数转换为异步上下文管理器
# 被 @asynccontextmanager 装饰的函数必须包含恰好一个 yield 语句，
# yield 之前的部分在进入上下文时执行（即服务启动），yield 之后的部分在退出上下文时执行（即服务关闭）
from contextlib import asynccontextmanager
from time import perf_counter

# --- 第三方库导入 ---
# FastAPI: Web 框架主类，创建应用实例、注册路由、配置中间件等的入口
import gradio as gr
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

# --- 项目内部模块导入 ---
from app.api.deps import build_sentinel_agent
# 各业务路由模块，每个 router 是一个 APIRouter 实例，包含一组相关的 HTTP 端点
from app.api.routes.health import router as health_router
from app.api.routes.reports import router as reports_router
from app.api.routes.subscriptions import router as subscriptions_router
# settings: 全局配置单例，从环境变量或 .env 文件加载应用配置
from app.core.config import settings
# ApiError: 自定义业务异常基类，所有业务层抛出的错误都应继承此类
# api_error_handler: 全局异常处理函数，将 ApiError 转换为标准化的 HTTP 错误响应
from app.core.errors import ApiError, api_error_handler, validation_error_handler
from app.core.logging import configure_logging, get_logger
# Base: SQLAlchemy ORM 声明性基类，所有数据库模型都继承自它，metadata 记录了全部表结构定义
from app.db.base import Base
from app.db.migrations import ensure_report_table, ensure_subscription_columns
# engine: SQLAlchemy 异步数据库引擎，管理连接池并执行 SQL 语句
from app.db.session import AsyncSessionLocal, engine
from app.services.scheduler import SubscriptionScheduler
from app.ui.gradio_app import build_gradio_app

logger = get_logger("main")


# @asynccontextmanager 装饰器将下方异步函数变为异步上下文管理器
# FastAPI 的 lifespan 参数接收此类对象，用于在应用启动/关闭时执行初始化和清理逻辑
# 参数 app: FastAPI 应用实例（由框架自动传入）
# 返回类型 AsyncIterator[None]: 标注这是一个产出 None 的异步迭代器（上下文管理器协议要求）
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """在应用启动时初始化数据库表结构并执行轻量迁移。"""
    configure_logging(settings.log_level, settings.log_format)
    # engine.begin(): 开启一个异步数据库事务
    # async with 确保事务在代码块结束后自动提交或回滚
    async with engine.begin() as connection:
        # run_sync: 在异步上下文中执行同步函数
        # Base.metadata.create_all 会检查所有继承 Base 的模型类，
        # 在数据库中创建尚不存在的对应数据表（不会删除或修改已有的表）
        await connection.run_sync(Base.metadata.create_all)
        await ensure_subscription_columns(connection)
        await ensure_report_table(connection)
    scheduler: SubscriptionScheduler | None = None
    if settings.scheduler_enabled:
        scheduler = SubscriptionScheduler(
            session_factory=AsyncSessionLocal,
            sentinel_agent=build_sentinel_agent(),
            tick_seconds=settings.scheduler_tick_seconds,
        )
        scheduler.start()
    else:
        logger.info("订阅调度器未启用")
    # yield: 上下文管理器的分界线
    # yield 之前的代码在服务启动时执行（建表），yield 暂停，服务开始接收请求
    # yield 之后的代码（本例为空）在服务关闭时执行（可用于清理资源、关闭连接等）
    try:
        yield
    finally:
        if scheduler is not None:
            await scheduler.stop()


# 应用工厂函数：集中创建和配置 FastAPI 实例
# 使用工厂模式而非模块级直接实例化，好处是：
#   1. 测试时可以创建多个独立的应用实例
#   2. 可以在不同环境下传入不同配置
#   3. 避免模块导入时产生副作用
def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例、异常处理器和业务路由。"""
    # FastAPI(): 创建应用实例
    # title: 应用的标题，会显示在自动生成的 Swagger UI 文档页面
    # lifespan: 绑定上面定义的生命周期管理器，框架会在启动/关闭时自动调用
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    # add_exception_handler: 注册全局异常处理器
    # 当路由处理函数或依赖项抛出 ApiError 类型的异常时，
    # 框架会自动调用 api_error_handler 将其转换为 HTTP 响应
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    # 其余路由均挂载到 /api 前缀下
    # 例如 subscriptions_router 中的 /subscriptions 端点，最终路径为 /api/subscriptions
    app.include_router(health_router, prefix="/api")
    app.include_router(subscriptions_router, prefix="/api")
    app.include_router(reports_router, prefix="/api")

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """记录每个 HTTP 请求的处理结果和耗时。"""
        started_at = perf_counter()
        response = await call_next(request)
        duration_ms = int((perf_counter() - started_at) * 1000)
        logger.info(
            "HTTP 请求处理完成",
            extra={
                "request_id": request.headers.get("x-request-id"),
                "duration_ms": duration_ms,
            },
        )
        return response

    return gr.mount_gradio_app(app, build_gradio_app(), path="/")


# 模块级变量：创建全局应用实例
# ASGI 服务器（如 uvicorn）默认查找名为 app 的变量作为应用入口
# 命令示例: uvicorn app.main:app --reload
app = create_app()
