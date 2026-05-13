from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    capacities_api_token: str = Field(
        validation_alias=AliasChoices("CAPACITIES_API_TOKEN", "CAPACITIES_API_KEY")
    )
    capacities_base_url: str = "https://api.capacities.io"
    capacities_timeout: float = 30.0


settings = Settings()
