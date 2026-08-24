"""Top-level FastAPI APIRouter for API v1 routes."""

from fastapi import APIRouter
from app.api.v1.endpoints import chat, meals

api_v1_router = APIRouter(prefix="/api/v1")

# Include sub-routers
api_v1_router.include_router(meals.router)
api_v1_router.include_router(chat.router)
