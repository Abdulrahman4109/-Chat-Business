from functools import lru_cache
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_base_url: str = "https://openrouter.ai/api/v1"
    openai_model: str = "gpt-4o-mini"
    mujarrad_public_key: str = ""
    mujarrad_secret_key: str = ""
    mujarrad_api_base: str = "https://www.mujarrad.com/api"
    mujarrad_space_url: str = "https://www.mujarrad.com/spaces/chat"
    mujarrad_segments_space_url: str = "https://www.mujarrad.com/spaces/example"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,https://chat-business.vercel.app"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def mujarrad_space_slug(self) -> str:
        path = urlparse(self.mujarrad_space_url).path.rstrip("/")
        return path.split("/")[-1] if path else "chat"

    @property
    def mujarrad_segments_space_slug(self) -> str:
        path = urlparse(self.mujarrad_segments_space_url).path.rstrip("/")
        return path.split("/")[-1] if path else "example"


@lru_cache
def get_settings() -> Settings:
    return Settings()

