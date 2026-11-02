"""应用配置。"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """从环境变量和 .env 文件加载的应用配置。"""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "智学路径 API"
    app_version: str = "1.0.0"
    debug: bool = False
    api_prefix: str = "/api"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    database_url: str = (
        "mysql+aiomysql://zhixue_dev:zhixue_dev_2026"
        "@127.0.0.1:3307/smart_learning_path?charset=utf8mb4"
    )
    jwt_secret_key: str = "please-change-this-secret-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080

    ai_base_url: str = "https://api.deepseek.com/v1"
    ai_api_key: str = "sk-ca66368b66794aec8bf95bb8fa316612"
    ai_chat_base_url: str = "https://api.deepseek.com/v1"
    ai_chat_model_name: str = "deepseek-v4-flash"
    ai_assistant_api_key: str = "sk-ca66368b66794aec8bf95bb8fa316612"
    ai_assistant_base_url: str = "https://api.deepseek.com/v1"
    ai_assistant_model_name: str = "deepseek-chat"

    @property
    def async_database_url(self) -> str:
        """返回强制使用 aiomysql 驱动的数据库连接地址。"""
        url = make_url(self.database_url.strip())
        if url.get_backend_name() != "mysql":
            raise ValueError("DATABASE_URL 必须使用 MySQL 数据库")
        return url.set(drivername="mysql+aiomysql").render_as_string(
            hide_password=False
        )


@lru_cache
def get_settings() -> Settings:
    """返回进程内复用的配置实例。"""
    return Settings()
