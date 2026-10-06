"""Review, approval and revisions of a document (SPEC 4, P6, 10.H; Phase 6).

A document is approved by its técnico responsável atribuído, and only when every condition holds:
it was assembled by the tool (pieces uploaded to be audited are only validated), it uses the
ficha-base confirmed last, every active section is reviewed, every block it uses is approved by
the curator (the block's current status, not the snapshot taken at assembly), and the last
validation has no critical alert open. The same conditions gate the official export.

Revision n of a document: file V<n>, header R<nn>, "rev. A, B…" in the interface.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assembly.assemble import confirmed_revision
from app.models import Document, FichaRevision, TemplateBlock, ValidationRun
from app.validation.engine import latest


def revision_label(n: int) -> str:
    """rev. A, B… Z, then AA, AB…"""
    label = ""
    n += 1
    while n:
        n, rest = divmod(n - 1, 26)
        label = chr(65 + rest) + label
    return label


def file_version(n: int) -> str:
    return f"V{n}"


def header_revision(n: int) -> str:
    return f"R{n:02d}"


@dataclass
class Condition:
    code: str  # assembled | ficha | sections | blocks | validation
    text: str  # what is required, for people
    ok: bool
    reason: str | None = None  # why it fails
    link: str | None = None  # where to resolve it, in the interface
    items: list[dict[str, Any]] = field(default_factory=list)  # sections concerned

    def as_json(self) -> dict[str, Any]:
        return {"code": self.code, "text": self.text, "ok": self.ok, "reason": self.reason,
                "link": self.link, "items": self.items}  # fmt: skip


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def block_statuses(db: Session, document: Document) -> dict[uuid.UUID, str]:
    ids = {s.block_id for s in document.sections if s.block_id}
    rows = db.execute(
        select(TemplateBlock.id, TemplateBlock.status).where(TemplateBlock.id.in_(ids))
    )
    return {block_id: status for block_id, status in rows}


def conditions(db: Session, document: Document) -> list[Condition]:
    project = document.project_id
    base = f"/projetos/{project}"
    assembled = document.origin == "assembled"
    existing = "Peça existente, carregada para auditoria: só se valida, não se exporta."
    out = [Condition("assembled", "Peça montada na aplicação", assembled,
                     None if assembled else existing)]  # fmt: skip

    confirmed = confirmed_revision(db, project)
    used = db.get(FichaRevision, document.ficha_revision_id)
    if confirmed is None:
        ficha_reason: str | None = "A ficha-base ainda não foi confirmada."
    elif confirmed.id != document.ficha_revision_id:
        before = used.label if used else "?"
        ficha_reason = (f"A ficha-base foi revista (rev. {confirmed.label}) depois da montagem "
                        f"(rev. {before}): volte a montar a peça.")  # fmt: skip
    else:
        ficha_reason = None
    out.append(Condition("ficha", "Ficha-base confirmada e usada na peça", ficha_reason is None,
                         ficha_reason, f"{base}/ficha"))  # fmt: skip

    active = [s for s in document.sections if s.active]
    open_sections = [s for s in active if s.status != "reviewed"]
    items = [{"section_id": str(s.id), "order": s.order, "title": s.title,
              "reason": s.status_note or "por rever"} for s in open_sections]  # fmt: skip
    done = len(active) - len(open_sections)
    link = f"{base}/documentos?doc={document.type}"
    if open_sections:
        link += f"&seccao={open_sections[0].id}"
    reason = _plural(len(open_sections), "secção por rever", "secções por rever")
    text = f"Todas as secções revistas ({done} de {len(active)})"
    out.append(Condition("sections", text, not open_sections,
                         reason if open_sections else None, link, items))  # fmt: skip

    statuses = block_statuses(db, document)
    pending = [s for s in active if s.block_id and statuses.get(s.block_id) != "approved"]
    out.append(Condition(
        "blocks", "Blocos usados aprovados pelo curador", not pending,
        _plural(len(pending), "bloco por aprovar", "blocos por aprovar") if pending else None,
        "/conhecimento?separador=blocos",
        [{"section_id": str(s.id), "order": s.order, "title": s.title,
          "reason": "bloco não aprovado"} for s in pending],
    ))  # fmt: skip

    newest = db.scalars(select(ValidationRun).where(ValidationRun.project_id == project)
                        .order_by(ValidationRun.created_at.desc()).limit(1)).first()  # fmt: skip
    run = latest(db, project)
    critical = 0 if run is None else sum(
        1 for i in run.issues if i.severity == "critical" and i.status == "open"
    )  # fmt: skip
    if newest is not None and newest.status in ("queued", "running"):
        validation_reason: str | None = "Validação em curso: espere pelo resultado."
    elif run is None:
        validation_reason = "O projeto ainda não foi validado."
    elif critical:
        validation_reason = _plural(critical, "alerta crítico aberto", "alertas críticos abertos")
    else:
        validation_reason = None
    out.append(Condition("validation", "Validação sem alertas críticos", validation_reason is None,
                         validation_reason, f"{base}/validacao"))  # fmt: skip
    return out


def ready(found: list[Condition]) -> bool:
    return all(c.ok for c in found)


def section_snapshot(document: Document) -> list[dict[str, Any]]:
    return [{"section_id": str(s.id), "order": s.order, "title": s.title,
             "version": s.current_version, "block_key": s.block_key, "active": s.active}
            for s in document.sections]  # fmt: skip
