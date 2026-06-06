from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """登录请求结构，接收本地账号和密码。"""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class RegisterRequest(BaseModel):
    """注册请求结构，限制用户名格式和密码长度。"""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    username: str = Field(min_length=2, max_length=18, pattern=r"^[A-Za-z0-9_]{2,18}$")
    password: str = Field(min_length=6, max_length=12)


class ChangePasswordRequest(BaseModel):
    """修改当前登录用户密码的请求结构。"""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    old_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=6, max_length=12)


class UserRead(BaseModel):
    """对外返回的用户基础信息，不包含密码哈希和会话信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    is_admin: bool
    created_at: datetime
