"""Meal Analysis and CRUD Endpoints Router."""

import io
import logging
from typing import Optional
from PIL import Image

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import ORJSONResponse

from app.api.deps import get_current_user
from app.core.config import MAX_IMAGE_SIZE_BYTES, validate_image_input
from app.schemas.auth import CurrentUser
from app.schemas.ingestion import IngestionState
from app.schemas.meal_api import (
    AnalyzedItemResponse,
    MealAnalysisResponse,
    MealAnalyzeRequest,
)
from app.services.langgraph.graph import ingestion_graph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meals", tags=["Meals"])


def compress_and_downscale_image(
    image_bytes: bytes, max_dim: int = 1024, quality: int = 80
) -> bytes:
    """Downscale image to max_dim x max_dim and compress to JPEG format for vision LLM optimization."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")

            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            output_buffer = io.BytesIO()
            img.save(output_buffer, format="JPEG", quality=quality, optimize=True)
            compressed = output_buffer.getvalue()
            logger.info(
                f"Image compression: {len(image_bytes)} bytes -> {len(compressed)} bytes "
                f"({round((1 - len(compressed)/len(image_bytes))*100, 1)}% reduction)"
            )
            return compressed
    except Exception as e:
        logger.warning(f"Image compression failed, using original bytes: {e}")
        return image_bytes


@router.post(
    "/analyze",
    response_model=MealAnalysisResponse,
    status_code=status.HTTP_200_OK,
    response_class=ORJSONResponse,
)
async def analyze_meal(
    request: Request,
    file: Optional[UploadFile] = File(None),
    image_url: Optional[str] = Form(None),
    user_caption: Optional[str] = Form(None),
    meal_type: Optional[str] = Form("lunch"),
    current_user: CurrentUser = Depends(get_current_user),
) -> MealAnalysisResponse:
    """Analyze a food image via LangGraph Workflow 1 (Vision Extraction & USDA Resolver).

    Supports multipart file upload or JSON payload with base64 data URI / image URL.
    Applies image compression guard (max 1024x1024) to reduce latency and bandwidth usage.
    """
    final_image_bytes: Optional[bytes] = None
    final_image_url: Optional[str] = None
    final_caption: Optional[str] = user_caption

    content_type = request.headers.get("content-type", "").lower()

    if "application/json" in content_type:
        try:
            body = await request.json()
            json_req = MealAnalyzeRequest(**body)
            final_caption = json_req.user_caption or final_caption
            if json_req.image_url:
                if json_req.image_url.startswith("data:image"):
                    # Extract base64 bytes if data URI
                    import base64

                    header, encoded = json_req.image_url.split(",", 1)
                    raw_b64_bytes = base64.b64decode(encoded)
                    final_image_bytes = compress_and_downscale_image(raw_b64_bytes)
                else:
                    final_image_url = validate_image_input(image_url=json_req.image_url)
        except HTTPException:
            raise
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON request body: {str(err)}",
            )
    elif file:
        raw_bytes = await file.read()
        if not raw_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded image file is empty.",
            )
        if len(raw_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Uploaded image payload exceeds 10MB limit.",
            )
        final_image_bytes = compress_and_downscale_image(raw_bytes)
    elif image_url:
        final_image_url = validate_image_input(image_url=image_url)

    if not final_image_bytes and not final_image_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either an image file upload, base64 data URI, or valid image_url must be provided.",
        )

    initial_state: IngestionState = {
        "image_bytes": final_image_bytes,
        "image_url": final_image_url,
        "user_caption": final_caption,
        "detected_items": [],
        "vision_confidence": 1.0,
        "usda_matches": {},
        "reconciled_items": [],
        "total_calories": 0.0,
        "total_protein_g": 0.0,
        "total_carbs_g": 0.0,
        "total_fat_g": 0.0,
        "aggregated_nutrients": {},
        "errors": [],
    }

    try:
        graph_result: IngestionState = await ingestion_graph.ainvoke(initial_state)
    except Exception as e:
        logger.exception("Error executing food vision ingestion graph")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze food vision image: {str(e)}",
        )

    analyzed_items = [
        AnalyzedItemResponse(
            food_name=item["food_name"],
            fdc_id=item.get("fdc_id"),
            portion_amount=item.get("portion_amount", 1.0),
            portion_unit=item.get("portion_unit", "serving"),
            gram_weight=item.get("gram_weight", 100.0),
            calories=item.get("calories", 0.0),
            protein_g=item.get("protein_g", 0.0),
            carbs_g=item.get("carbs_g", 0.0),
            fat_g=item.get("fat_g", 0.0),
            is_fallback=item.get("is_fallback", False),
            raw_usda_nutrients=item.get("raw_usda_nutrients", {}),
        )
        for item in graph_result.get("reconciled_items", [])
    ]

    return MealAnalysisResponse(
        detected_items=analyzed_items,
        total_calories=graph_result.get("total_calories", 0.0),
        total_protein_g=graph_result.get("total_protein_g", 0.0),
        total_carbs_g=graph_result.get("total_carbs_g", 0.0),
        total_fat_g=graph_result.get("total_fat_g", 0.0),
        aggregated_nutrients=graph_result.get("aggregated_nutrients", {}),
        confidence_score=graph_result.get("vision_confidence", 1.0),
        warnings=graph_result.get("errors", []),
    )
