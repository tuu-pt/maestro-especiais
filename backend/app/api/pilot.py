"""The pilot (Phase 8): active time per step, measured by the frontend while people work."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.projects import get_project
from app.auth import CurrentUser
from app.db import get_session
from app.models import AuditEvent
from app.models.pilot import PilotTime
from app.pilot.steps import step_for

router = APIRouter(tags=["piloto"])
DB = Annotated[Session, Depends(get_session)]
HEARTBEAT_MAX_S = 60  # one heartbeat never adds more than this [A CONFIRMAR]


class HeartbeatIn(BaseModel):
    screen: str = Field(max_length=40)  # the route of the screen: ficha, documentos, revisao…
    hint: str | None = Field(default=None, max_length=20)  # inside a screen: mdj, cte, formularios
    seconds: int = Field(default=30, ge=1)


def reviewed(db: Session, project_id: uuid.UUID) -> bool:
    """The pieces of the project were sent for review at least once."""
    return bool(db.scalar(select(exists().where(
        AuditEvent.action == "review.requested",
        AuditEvent.payload["project_id"].astext == str(project_id)))))  # fmt: skip


@router.post("/projects/{project_id}/pilot/heartbeat", status_code=status.HTTP_204_NO_CONTENT)
def heartbeat(project_id: uuid.UUID, body: HeartbeatIn, db: DB, user: CurrentUser) -> Response:
    """Adds the active seconds to the step; a screen outside a project's work adds nothing.

    Not audited: one every 30 s would drown the history.
    """
    project = get_project(db, project_id)
    step = step_for(body.screen, body.hint, reviewed(db, project.id))
    if step is not None:
        seconds = min(body.seconds, HEARTBEAT_MAX_S)
        row = insert(PilotTime).values(
            id=uuid.uuid4(), project_id=project.id, user_id=user.id, step=step,
            day=datetime.now(UTC).date(), seconds=seconds,
        )  # fmt: skip
        added = {"seconds": PilotTime.seconds + seconds, "updated_at": datetime.now(UTC)}
        db.execute(row.on_conflict_do_update(constraint="uq_pilot_time", set_=added))
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
