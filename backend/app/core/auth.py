"""JWT 令牌生成与验证。"""

from datetime import UTC, datetime, timedelta
from typing import Literal

from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

settings = get_settings()


class InvalidTokenError(Exception):
    """JWT 无效、过期或声明不合法。"""


class TokenPayload(BaseModel):
    """本系统签发的 JWT 载荷。"""

    sub: str
    username: str
    token_type: Literal["access"]
    iat: int
    exp: int


def create_access_token(
    *,
    user_id: int,
    username: str,
    expires_delta: timedelta | None = None,
) -> str:
    """生成有效期默认 7 天的访问令牌。"""
    now = datetime.now(UTC)
    expires_at = now + (
        expires_delta
        or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {
        "sub": str(user_id),
        "username": username,
        "token_type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> TokenPayload:
    """验证 JWT 签名和有效期，并返回令牌载荷。"""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        token_payload = TokenPayload.model_validate(payload)
    except (JWTError, ValidationError, ValueError) as exc:
        raise InvalidTokenError("登录状态已失效，请重新登录") from exc

    if token_payload.token_type != "access":
        raise InvalidTokenError("不支持的令牌类型")

    return token_payload
