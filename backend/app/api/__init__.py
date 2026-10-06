"""HTTP API. Every router checks the caller's roles."""

from fastapi import APIRouter

from app.api import (
    audit,
    documents,
    drafting,
    editor,
    events,
    exports,
    ficha,
    forms,
    knowledge,
    library,
    me,
    projects,
    review,
    validation,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(me.router)
api_router.include_router(projects.router)
api_router.include_router(events.router)
api_router.include_router(ficha.router)
api_router.include_router(audit.router)
api_router.include_router(knowledge.router)
api_router.include_router(library.router)
api_router.include_router(documents.router)
api_router.include_router(drafting.router)
api_router.include_router(editor.router)
api_router.include_router(forms.router)
api_router.include_router(validation.router)
api_router.include_router(review.router)
api_router.include_router(exports.router)
