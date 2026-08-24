"""Top-level FastAPI APIRouter for API v1 routes."""

from fastapi import APIRouter

api_v1_router = APIRouter(prefix="/api/v1")

# Sub-routers (meals, chat, dashboard, profile) will be included here as subtasks are implemented.
