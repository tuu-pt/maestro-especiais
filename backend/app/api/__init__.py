"""HTTP API. Every router checks the caller's roles."""

from fastapi import APIRouter

from app.api import events, me, projects

api_router = APIRouter(prefix="/api")
api_router.include_router(me.router)
api_router.include_router(projects.router)
api_router.include_router(events.router)
