<<<<<<< Updated upstream
=======
import os
from pathlib import Path
from typing import ClassVar

import yaml
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_name: str = "comate-agent"
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Database
    database_url: str = "postgresql+asyncpg://postgres:${DB_PASSWORD}@localhost:5432/comate"

    # Email
    email_host: str = "smtp.qq.com"
    email_port: int = 465
    email_user: str = ""
    email_pass: str = ""
    email_from: str = "伴行agent <noreply@comate.ai>"

    # Model - DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # JWT
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 72

    model_config: ClassVar[dict] = {
        "env_file": "../config/.env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @classmethod
    def _load_dotenv(cls):
        """加载 .env 文件到环境变量"""
        env_path = Path(__file__).parent.parent.parent / "config" / ".env"
        if env_path.exists():
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and not os.environ.get(key):
                        os.environ[key] = val

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Settings":
        cls._load_dotenv()
        path = Path(path)
        if not path.exists():
            return cls()
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return cls(
            app_name=raw.get("app", {}).get("name", "comate-agent"),
            debug=raw.get("app", {}).get("debug", False),
            database_url=os.path.expandvars(raw.get("database", {}).get("url", cls().database_url)),
            email_host=raw.get("email", {}).get("host", cls().email_host),
            email_port=raw.get("email", {}).get("port", cls().email_port),
            email_user=os.path.expandvars(raw.get("email", {}).get("user", cls().email_user)),
            email_pass=os.path.expandvars(raw.get("email", {}).get("pass", cls().email_pass)),
            email_from=os.path.expandvars(raw.get("email", {}).get("from", cls().email_from)),
            deepseek_api_key=os.path.expandvars(raw.get("model", {}).get("default", {}).get("api_key", "")),
            deepseek_base_url=raw.get("model", {}).get("default", {}).get("base_url", cls().deepseek_base_url),
            deepseek_model=raw.get("model", {}).get("default", {}).get("model", cls().deepseek_model),
            jwt_secret=os.path.expandvars(raw.get("jwt", {}).get("secret", cls().jwt_secret)),
            jwt_algorithm=raw.get("jwt", {}).get("algorithm", cls().jwt_algorithm),
            jwt_expire_hours=raw.get("jwt", {}).get("expire_hours", cls().jwt_expire_hours),
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
        _settings = Settings.from_yaml(config_path)
    return _settings
>>>>>>> Stashed changes
