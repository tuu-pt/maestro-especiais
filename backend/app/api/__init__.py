"""HTTP API. Every router checks the caller's roles."""

from fastapi import APIRouter

from app.api import (
    audit,
    documents,
    drafting,
    editor,
    equipment,
    events,
    exports,
    ficha,
    forms,
    knowledge,
    library,
    me,
    project_equipment,
    projects,
    review,
    session,
    settings,
    validation,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(me.router)
api_router.include_router(session.router)
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
api_router.include_router(equipment.router)
api_router.include_router(project_equipment.router)
api_router.include_router(settings.router)
