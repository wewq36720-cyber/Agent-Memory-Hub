"""Application configuration loaded from environment / .env."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # MySQL
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_root_password: str
    mysql_database: str = "distiller_hub"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    # JSONL
    jsonl_log_dir: Path = Path("./logs")

    # Timezone
    tz: str = "Asia/Shanghai"

    @property
    def mysql_url(self) -> str:
        """SQLAlchemy 连接字符串（同步驱动 PyMySQL）。"""
        return (
            f"mysql+pymysql://root:{self.mysql_root_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            f"?charset=utf8mb4"
        )


settings = Settings()
