"""用户认证相关 Schema。"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class _PasswordMixin(BaseModel):
    """校验 bcrypt 可接受的最大密码长度。"""

    password: str

    @field_validator("password")
    @classmethod
    def validate_password_length(cls, value: str) -> str:
        """确保密码不超过 bcrypt 的 72 字节限制。"""
        if len(value.encode("utf-8")) > 72:
            raise ValueError("密码 UTF-8 编码后不能超过 72 字节")
        return value


class RegisterRequest(_PasswordMixin):
    """用户注册请求。"""

    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        """去除用户名首尾空白并禁止空用户名。"""
        normalized = value.strip()
        if not normalized:
            raise ValueError("用户名不能为空")
        return normalized


class LoginRequest(_PasswordMixin):
    """用户登录请求。"""

    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=72)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        """去除用户名首尾空白。"""
        normalized = value.strip()
        if not normalized:
            raise ValueError("用户名不能为空")
        return normalized


class UserBrief(BaseModel):
    """登录响应中的精简用户信息。"""

    id: int
    username: str
    nickname: str | None = None
    avatar_url: str | None = None


class UserProfile(BaseModel):
    """当前登录用户的完整公开信息。"""

    id: int
    username: str
    email: str
    nickname: str | None
    bio: str | None
    avatar_url: str | None
    created_at: datetime


class UpdateProfileRequest(BaseModel):
    """修改当前用户公开资料。"""

    nickname: str | None = Field(default=None, max_length=50)
    bio: str | None = Field(default=None, max_length=280)
    avatar_url: str | None = Field(default=None, max_length=255)

    @field_validator("nickname", "bio", "avatar_url")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """去除首尾空白，空字符串按未填写处理。"""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ChangePasswordRequest(BaseModel):
    """修改当前用户密码。"""

    old_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("old_password", "new_password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        """确保密码不超过 bcrypt 的 72 字节限制。"""
        if len(value.encode("utf-8")) > 72:
            raise ValueError("密码 UTF-8 编码后不能超过 72 字节")
        return value


class AvatarUploadData(BaseModel):
    """头像上传结果。"""

    avatar_url: str


class RegisterData(BaseModel):
    """注册成功数据。"""

    user_id: int
    username: str


class LoginData(BaseModel):
    """登录成功数据。"""

    token: str
    user: UserBrief
