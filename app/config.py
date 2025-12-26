from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    debug: bool = False

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5433/locus_guide"

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # Google OAuth
    google_client_id: str = ""

    # Email (for password reset - not implemented yet)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""

    # Cities API settings
    cities_default_limit: int = 10
    cities_max_limit: int = 50
    cities_min_query_length: int = 1
    cities_languages: list = ["en", "ru", "de"]
    geoip_enabled: bool = True
    geoip_url: str = "http://ip-api.com/json/{ip}"
    data_dir: str = "./data"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
