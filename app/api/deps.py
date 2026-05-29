"""
定义 API 层依赖别名 `DbSession`，统一注入 SQLAlchemy 异步数据库会话。
"""

# Annotated: Python 3.9+ 的类型注解工具，允许在类型标注上附加元数据
# 语法: Annotated[基础类型, 元数据1, 元数据2, ...]
# 在 FastAPI 语境中，元数据用于声明依赖注入、参数校验等框架级行为
from typing import Annotated

# Depends: FastAPI 依赖注入的核心构造器
# 当函数参数声明为 Depends(某个可调用对象) 时，FastAPI 会在请求处理前
# 自动调用该可调用对象，将其返回值注入到参数中
from fastapi import Depends
# AsyncSession: SQLAlchemy 异步数据库会话类
# 会话封装了数据库连接，提供 CRUD 操作接口，并管理事务生命周期
from sqlalchemy.ext.asyncio import AsyncSession

# get_session: 异步生成器函数，创建并管理 AsyncSession 的生命周期
# 使用 yield 模式确保请求结束后会话自动关闭
from app.db.session import get_session
from app.services.github_client import HttpRepositoryClient
from app.services.notifications import NullNotificationSender
from app.services.reporting import MarkdownReportRenderer
from app.services.sentinel import SentinelAgent

# Annotated[AsyncSession, Depends(get_session)] 的含义：
#   - 基础类型为 AsyncSession → 告诉 IDE 和类型检查器这个参数是数据库会话
#   - 元数据为 Depends(get_session) → 告诉 FastAPI 在处理请求时自动调用
#     get_session() 获取会话实例并注入
# 将其赋值给 DbSession 类型别名后，路由函数中只需写：
#   async def my_route(session: DbSession):
# 而不需要每次都写：
#   async def my_route(session: AsyncSession = Depends(get_session)):
# 这消除了重复代码，且切换会话来源时只需修改此文件一处
DbSession = Annotated[AsyncSession, Depends(get_session)]


async def get_sentinel_agent() -> SentinelAgent:
    """构建 Sentinel 编排服务，集中装配抓取、渲染和通知实现。"""
    return SentinelAgent(
        github_client=HttpRepositoryClient(),
        report_renderer=MarkdownReportRenderer(),
        notification_sender=NullNotificationSender(),
    )


SentinelAgentDep = Annotated[SentinelAgent, Depends(get_sentinel_agent)]
