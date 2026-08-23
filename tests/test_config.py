import pytest
from app.core.config import MAX_IMAGE_SIZE_BYTES, settings, validate_image_input


def test_settings_defaults():
    """Verify default configurations for USDA API and Vision LLM settings."""
    assert settings.USDA_API_KEY == "DEMO_KEY" or settings.USDA_API_KEY is not None
    assert settings.USDA_API_BASE_URL == "https://api.nal.usda.gov/fdc/v1"
    assert settings.VISION_LLM_MODEL == "gpt-4o"


def test_validate_image_input_bytes_success():
    """Verify image_bytes payload under 10MB formats base64 data URI correctly."""
    sample_bytes = b"fake-image-binary-data"
    result = validate_image_input(image_bytes=sample_bytes)
    assert result.startswith("data:image/jpeg;base64,")


def test_validate_image_input_bytes_oversized():
    """Verify image_bytes exceeding 10MB raises ValueError."""
    oversized_bytes = b"0" * (MAX_IMAGE_SIZE_BYTES + 1)
    with pytest.raises(ValueError, match="10MB"):
        validate_image_input(image_bytes=oversized_bytes)


def test_validate_image_input_url_success():
    """Verify valid HTTP/HTTPS image URL passes validation."""
    url = "https://example.com/food.jpg"
    result = validate_image_input(image_url=url)
    assert result == url


def test_validate_image_input_url_invalid():
    """Verify invalid URL format raises ValueError."""
    with pytest.raises(ValueError, match="Invalid image URL"):
        validate_image_input(image_url="ftp://example.com/food.jpg")


def test_validate_image_input_empty():
    """Verify missing both image inputs raises ValueError."""
    with pytest.raises(
        ValueError, match="Either image_bytes or image_url must be provided"
    ):
        validate_image_input()
