"""HTTP API. Every router checks the caller's roles."""

from fastapi import APIRouter

from app.api import me

api_router = APIRouter(prefix="/api")
api_router.include_router(me.router)
