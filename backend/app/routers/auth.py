"""用户注册、登录与当前用户信息路由。"""

import asyncio
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import InvalidTokenError, create_access_token, decode_access_token
from app.core.database import get_db
from app.core.response import ApiResponse
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import (
    AvatarUploadData,
    ChangePasswordRequest,
    LoginData,
    LoginRequest,
    RegisterData,
    RegisterRequest,
    UpdateProfileRequest,
    UserBrief,
    UserProfile,
)

router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(bearer_scheme),
]
AVATAR_DIR = (
    Path(__file__).resolve().parents[2] / "data" / "media" / "avatars"
)
AVATAR_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_AVATAR_BYTES = 2 * 1024 * 1024


async def get_current_user(
    credentials: BearerCredentials,
    db: DatabaseSession,
) -> User:
    """解析 Bearer Token 并返回当前用户。"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload.sub)
    except (InvalidTokenError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或登录状态已失效",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def _to_user_profile(user: User) -> UserProfile:
    """把用户模型转换为资料响应。"""
    return UserProfile(
        id=user.id,
        username=user.username,
        email=user.email,
        nickname=user.nickname,
        bio=user.bio,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
    )


@router.post(
    "/register",
    response_model=ApiResponse[RegisterData],
    status_code=status.HTTP_200_OK,
    summary="注册用户",
)
async def register(
    payload: RegisterRequest,
    db: DatabaseSession,
) -> ApiResponse[RegisterData]:
    """创建新用户，用户名和邮箱均不可重复。"""
    existing_user = await db.scalar(
        select(User).where(
            or_(
                User.username == payload.username,
                User.email == str(payload.email).lower(),
            )
        )
    )
    if existing_user is not None:
        if existing_user.username == payload.username:
            message = "用户名已存在"
        else:
            message = "邮箱已被注册"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    password_hash = await asyncio.to_thread(hash_password, payload.password)
    user = User(
        username=payload.username,
        email=str(payload.email).lower(),
        password_hash=password_hash,
    )
    db.add(user)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名或邮箱已存在",
        ) from exc

    await db.refresh(user)
    return ApiResponse[RegisterData](
        code=status.HTTP_200_OK,
        message="注册成功",
        data=RegisterData(user_id=user.id, username=user.username),
    )


@router.post(
    "/login",
    response_model=ApiResponse[LoginData],
    status_code=status.HTTP_200_OK,
    summary="用户登录",
)
async def login(
    payload: LoginRequest,
    db: DatabaseSession,
) -> ApiResponse[LoginData]:
    """校验用户名和密码并签发 7 天有效的 JWT。"""
    user = await db.scalar(
        select(User).where(User.username == payload.username)
    )
    password_is_valid = False
    if user is not None:
        password_is_valid = await asyncio.to_thread(
            verify_password,
            payload.password,
            user.password_hash,
        )

    if user is None or not password_is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user_id=user.id, username=user.username)
    return ApiResponse[LoginData](
        code=status.HTTP_200_OK,
        message="登录成功",
        data=LoginData(
            token=token,
            user=UserBrief(
                id=user.id,
                username=user.username,
                nickname=user.nickname,
                avatar_url=user.avatar_url,
            ),
        ),
    )


@router.get(
    "/profile",
    response_model=ApiResponse[UserProfile],
    status_code=status.HTTP_200_OK,
    summary="获取当前用户信息",
)
async def get_profile(
    current_user: CurrentUser,
) -> ApiResponse[UserProfile]:
    """返回 Bearer Token 对应的用户公开信息。"""
    return ApiResponse[UserProfile](
        code=status.HTTP_200_OK,
        message="获取用户信息成功",
        data=_to_user_profile(current_user),
    )


@router.patch(
    "/profile",
    response_model=ApiResponse[UserProfile],
    status_code=status.HTTP_200_OK,
    summary="修改当前用户资料",
)
async def update_profile(
    payload: UpdateProfileRequest,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[UserProfile]:
    """更新昵称、个人简介或外链头像。"""
    updates = payload.model_fields_set
    if "nickname" in updates:
        current_user.nickname = payload.nickname
    if "bio" in updates:
        current_user.bio = payload.bio
    if "avatar_url" in updates:
        current_user.avatar_url = payload.avatar_url
    await db.commit()
    await db.refresh(current_user)
    return ApiResponse[UserProfile](
        code=status.HTTP_200_OK,
        message="个人资料已更新",
        data=_to_user_profile(current_user),
    )


@router.post(
    "/password",
    response_model=ApiResponse[dict[str, bool]],
    status_code=status.HTTP_200_OK,
    summary="修改当前用户密码",
)
async def change_password(
    payload: ChangePasswordRequest,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> ApiResponse[dict[str, bool]]:
    """校验旧密码后保存新的密码哈希。"""
    password_is_valid = await asyncio.to_thread(
        verify_password,
        payload.old_password,
        current_user.password_hash,
    )
    if not password_is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前密码不正确",
        )
    if payload.old_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码不能与当前密码相同",
        )

    current_user.password_hash = await asyncio.to_thread(
        hash_password,
        payload.new_password,
    )
    await db.commit()
    return ApiResponse[dict[str, bool]](
        code=status.HTTP_200_OK,
        message="密码修改成功",
        data={"changed": True},
    )


@router.post(
    "/avatar",
    response_model=ApiResponse[AvatarUploadData],
    status_code=status.HTTP_200_OK,
    summary="上传当前用户头像",
)
async def upload_avatar(
    db: DatabaseSession,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File()],
) -> ApiResponse[AvatarUploadData]:
    """保存 PNG、JPEG、WebP 或 GIF 头像并返回访问地址。"""
    content_type = (file.content_type or "").lower()
    suffix = AVATAR_TYPES.get(content_type)
    if suffix is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="头像仅支持 PNG、JPEG、WebP 或 GIF 格式",
        )

    content = await file.read(MAX_AVATAR_BYTES + 1)
    await file.close()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传的头像文件为空",
        )
    if len(content) > MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="头像文件不能超过 2 MB",
        )

    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"user_{current_user.id}_{uuid4().hex}{suffix}"
    target = AVATAR_DIR / filename
    await asyncio.to_thread(target.write_bytes, content)

    old_avatar = current_user.avatar_url
    current_user.avatar_url = f"/media/avatars/{filename}"
    await db.commit()

    if old_avatar and old_avatar.startswith("/media/avatars/"):
        old_path = AVATAR_DIR / Path(old_avatar).name
        if old_path != target and old_path.is_file():
            await asyncio.to_thread(old_path.unlink, missing_ok=True)

    return ApiResponse[AvatarUploadData](
        code=status.HTTP_200_OK,
        message="头像已更新",
        data=AvatarUploadData(avatar_url=current_user.avatar_url),
    )
