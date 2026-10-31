"""应用配置。"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """从环境变量和 .env 文件加载的应用配置。"""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "智学路径 API"
    app_version: str = "0.1.0"
    debug: bool = False
    api_prefix: str = "/api"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    secret_key: str = "please-change-this-secret-key"
    access_token_expire_minutes: int = 1440

    ai_base_url: str = "https://api.deepseek.com/v1"
    ai_api_key: str = ""
    ai_model: str = "deepseek-chat"

    @property
    def database_url(self) -> str:
        """返回指向后端目录内 SQLite 文件的异步连接地址。"""
        database_path = (BASE_DIR / "smart_learning_path.db").as_posix()
        return f"sqlite+aiosqlite:///{database_path}"


@lru_cache
def get_settings() -> Settings:
    """返回进程内复用的配置实例。"""
    return Settings()
