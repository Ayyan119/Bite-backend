from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings validated via Pydantic v2."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    APP_ENV: str = Field(default="development", description="Application environment")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # Database
    SUPABASE_POSTGRES_DIRECT_URL: str = Field(
        default="postgresql://postgres:password@localhost:5432/bite_db",
        description="Direct PostgreSQL connection string",
    )

    # API Keys
    GEMINI_API_KEY: str | None = Field(default=None, description="Gemini API Key")
    OPENAI_API_KEY: str | None = Field(default=None, description="OpenAI API Key")
    USDA_API_KEY: str | None = Field(
        default=None, description="USDA FoodData Central API Key"
    )
    SUPABASE_JWT_SECRET: str | None = Field(
        default=None, description="Supabase JWT Verification Secret"
    )


settings = Settings()
