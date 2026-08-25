import base64
from datetime import datetime
import os
import zoneinfo
import dotenv

dotenv.load_dotenv()

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

    # API Keys & LLM Config
    GEMINI_API_KEY: str | None = Field(default=None, description="Gemini API Key")
    OPENAI_API_KEY: str | None = Field(default=None, description="OpenAI API Key")
    USDA_API_KEY: str = Field(
        default="DEMO_KEY", description="USDA FoodData Central API Key"
    )
    USDA_API_BASE_URL: str = Field(
        default="https://api.nal.usda.gov/fdc/v1",
        description="USDA FoodData Central API Base URL",
    )
    VISION_LLM_MODEL: str = Field(
        default="gpt-4o",
        description="Vision LLM model identifier for complex visual analysis",
    )
    FAST_LLM_MODEL: str = Field(
        default="gpt-4o-mini",
        description="Fast LLM model identifier for fallback macro estimation and fast tasks",
    )
    SUPABASE_JWT_SECRET: str | None = Field(
        default=None, description="Supabase JWT Verification Secret"
    )


settings = Settings()

MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit


def validate_image_input(
    image_bytes: bytes | None = None, image_url: str | None = None
) -> str:
    """Validate image payload (bytes or URL) and enforce maximum 10MB size limit.

    Returns the formatted base64 data URI string or verified image URL.
    Raises ValueError if neither input is valid or if size exceeds 10MB.
    """
    if not image_bytes and not image_url:
        raise ValueError("Either image_bytes or image_url must be provided.")

    if image_bytes:
        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise ValueError("Image payload exceeds maximum allowed size of 10MB.")
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"

    if image_url:
        clean_url = image_url.strip()
        if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
            raise ValueError("Invalid image URL. Must start with http:// or https://")
        return clean_url

    raise ValueError("Invalid image input provided.")


PK_TZ = zoneinfo.ZoneInfo("Asia/Karachi")


def get_pakistan_now() -> datetime:
    """Returns current datetime in Pakistan Time Zone (Asia/Karachi, PKT / UTC+5)."""
    return datetime.now(PK_TZ)


def get_local_now(client_tz_name: str | None = None) -> datetime:
    """Returns current datetime in Pakistan Time Zone (Asia/Karachi)."""
    return get_pakistan_now()
