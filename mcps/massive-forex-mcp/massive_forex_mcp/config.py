from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

    massive_api_key: str | None = None
    polygon_api_key: str | None = None
    massive_api_base: str = "https://api.polygon.io"
    massive_request_timeout: float = 30.0

    @property
    def api_key(self) -> str:
        key = self.massive_api_key or self.polygon_api_key
        if not key:
             raise RuntimeError(
                "Missing MASSIVE_API_KEY. Set MASSIVE_API_KEY in the environment or in a .env file."
            )
        return key

    @property
    def api_base(self) -> str:
        return self.massive_api_base.rstrip("/")

settings = Settings()
