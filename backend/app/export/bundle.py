"""The set of the project (SPEC 10.H, 11; Phase 6): MDJ, CTE, ficha eletrotécnica, identification
and term in one .zip, with the TUU names and a manifest.

Official: every document assembled by the tool approved by its técnico responsável, with every
condition of app.review met; the files take the official names and must pass every fidelity
check, or the export fails. Draft: always possible; watermark in every page and in every name.
Each file is kept in the S3 bucket with its hash (keys never hold the file names) and the export
is recorded in the audit. Personal values are only written into the files, never logged.
"""

import hashlib
import io
import json
import logging
import uuid
import zipfile
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assembly.assemble import confirmed_revision
from app.assembly.values import ValueSource
from app.audit import record
from app.config import Settings
from app.export import (
    PHASE_CODES,
    SPECIALTY_CODE,
    WATERMARK,
    ExportRefused,
    draft_name,
    official_name,
)
from app.export.checks import check_docx, check_xlsm, to_pdf
from app.export.docx import DOCX, expected_counts, export_docx
from app.forms.fill import FORMS, fill, template
from app.models import Document, Export, Project
from app.profiles import revision_profile
from app.progress import Publish
from app.review import conditions, file_version, revision_label
from app.storage import ObjectStore
from app.validation.engine import latest

logger = logging.getLogger(__name__)
XLSM = "application/vnd.ms-excel.sheet.macroEnabled.12"
PDF = "application/pdf"
ZIP = "application/zip"
# The forms in the set: piece name in the file, its kind, extension and media type
FORM_FILES = (("FichaEletrotecnica", "ficha_eletrotecnica", "xlsm", XLSM),
              ("IdentificacaoProjeto", "identificacao", "docx", DOCX),
              ("TermoResponsabilidade", "termo", "docx", DOCX))  # fmt: skip
FE_SHEET_PART = "xl/worksheets/sheet1.xml"


def _name(user_id: str | None) -> str | None:
    from app.api.review import user_name

    return user_name(user_id)


def pieces(db: Session, project_id: uuid.UUID) -> list[Document]:
    """The MDJ and CTE of the set: the latest assembled document of each type."""
    rows = db.scalars(select(Document).where(Document.project_id == project_id,
                                             Document.origin == "assembled")
                      .order_by(Document.created_at.desc())).all()  # fmt: skip
    found: dict[str, Document] = {}
    for d in rows:
        found.setdefault(d.type, d)
    return [found[t] for t in ("MDJ", "CTE") if t in found]


def refusals(db: Session, project: Project, kind: str) -> list[str]:
    """Why this export cannot be made now (empty: it can)."""
    reasons = []
    if confirmed_revision(db, project.id) is None:
        reasons.append("A ficha-base ainda não foi confirmada.")
    documents = pieces(db, project.id)
    if not documents:
        reasons.append("Ainda não há MDJ nem CTE montados na aplicação.")
    if kind == "official":
        for d in documents:
            failing = [c.reason or c.text for c in conditions(db, d) if not c.ok]
            if d.status != "approved":
                failing.append("ainda não foi aprovado pelo técnico responsável")
            reasons += [f"{d.type}: {r}" for r in failing]
        if {d.type for d in documents} != {"MDJ", "CTE"}:
            reasons.append("O conjunto oficial precisa do MDJ e do CTE.")
    return reasons


def queue_export(db: Session, project: Project, kind: str, with_pdf: bool,
                 user_id: str) -> Export:  # fmt: skip
    reasons = refusals(db, project, kind)
    if reasons:
        raise ExportRefused(reasons)
    documents = pieces(db, project.id)
    version = file_version(max(d.revision for d in documents)) if documents else "V0"
    export = Export(project_id=project.id, kind=kind, with_pdf=with_pdf, version=version,
                    created_by=user_id)  # fmt: skip
    db.add(export)
    db.flush()
    return export


def _event(export: Export) -> dict[str, Any]:
    return {"type": "export", "export_id": str(export.id), "kind": export.kind,
            "status": export.status, "message": export.message}  # fmt: skip


def _ignored(db: Session, project_id: uuid.UUID) -> list[dict[str, Any]]:
    """Warnings and alerts a person ignored, with the justification (SPEC 10.H)."""
    run = latest(db, project_id)
    if run is None:
        return []
    return [{"rule": i.rule_id, "severity": i.severity, "piece": i.location.get("piece"),
             "reason": i.ignored_reason, "by": _name(i.resolved_by),
             "at": i.resolved_at.isoformat(timespec="seconds") if i.resolved_at else None}
            for i in run.issues if i.status == "ignored"]  # fmt: skip


def build(db: Session, store: ObjectStore, settings: Settings, export: Export
          ) -> tuple[list[dict[str, Any]], dict[str, bytes], list[str], list[str]]:  # fmt: skip
    """(files, contents by name, problems, notes) of the set."""
    project = db.get(Project, export.project_id)
    revision = confirmed_revision(db, export.project_id)
    assert project is not None and revision is not None
    official = export.kind == "official"
    files: list[dict[str, Any]] = []
    contents: dict[str, bytes] = {}
    problems: list[str] = []
    notes: list[str] = []

    def add(name: str, piece: str, data: bytes, media_type: str, rev: str | None) -> None:
        contents[name] = data
        files.append({"name": name, "piece": piece, "revision": rev, "media_type": media_type,
                      "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})  # fmt: skip

    for document in pieces(db, export.project_id):
        exported = export_docx(db, store, settings, document, official=official)
        report = check_docx(exported.data, expected=expected_counts(db, document),
                            official=official, watermark=None if official else WATERMARK,
                            libreoffice=False)  # fmt: skip
        problems += [f"{exported.name}: {p}" for p in report.problems]
        add(exported.name, document.type, exported.data, DOCX, revision_label(document.revision))
        if export.with_pdf:
            pdf, problem = to_pdf(exported.data, "docx")
            if pdf is not None:
                add(exported.name.rsplit(".", 1)[0] + ".pdf", document.type, pdf, PDF,
                    revision_label(document.revision))  # fmt: skip
            elif problem:
                problems.append(f"{exported.name}: {problem}")
            else:
                notes.append("PDF não gerado: o LibreOffice não está instalado neste servidor.")
    values = ValueSource.load(db, revision, revision_profile(db, settings, revision))
    for piece, kind, ext, media_type in FORM_FILES:
        filled = fill(kind, values, None if official else WATERMARK)
        name = (official_name(project.code, piece, project.phase, export.version, ext)
                if official else draft_name(project.code, piece, ext))  # fmt: skip
        if kind == "ficha_eletrotecnica":
            report = check_xlsm(filled.data, template(FORMS[kind].template), sheet=FE_SHEET_PART)
        else:
            report = check_docx(filled.data, official=official,
                                watermark=None if official else WATERMARK,
                                libreoffice=False)  # fmt: skip
        problems += [f"{name}: {p}" for p in report.problems]
        add(name, kind, filled.data, media_type, None)
        files[-1]["by_hand"] = filled.by_hand
    return files, contents, problems, list(dict.fromkeys(notes))


def manifest(db: Session, export: Export, files: list[dict[str, Any]], problems: list[str],
             notes: list[str]) -> dict[str, Any]:  # fmt: skip
    project = db.get(Project, export.project_id)
    revision = confirmed_revision(db, export.project_id)
    assert project is not None
    return {
        "projeto": {"codigo": project.code, "nome": project.name,
                    "fase": PHASE_CODES.get(project.phase, "PE"), "especialidade": SPECIALTY_CODE},
        "tipo": "oficial" if export.kind == "official" else "rascunho",
        "versao": export.version,
        "criado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "criado_por": _name(export.created_by),
        "ficha_base": f"rev. {revision.label}" if revision else None,
        "pecas": [
            {"tipo": d.type, "revisao": revision_label(d.revision),
             "versao": file_version(d.revision), "estado": d.status,
             "responsavel": _name(d.responsible_user_id), "aprovada_por": _name(d.approved_by),
             "aprovada_em": d.approved_at.isoformat(timespec="seconds") if d.approved_at else None,
             "cabecalho_data": d.header_date}
            for d in pieces(db, export.project_id)
        ],
        "ficheiros": [{k: f[k] for k in ("name", "piece", "revision", "sha256", "size")}
                      | ({"por_preencher": f["by_hand"]} if f.get("by_hand") else {})
                      for f in files],
        "avisos_ignorados": _ignored(db, export.project_id),
        "verificacoes": {"problemas": problems, "notas": notes},
        "notas": ["Os formulários saem sem data nem assinatura: o técnico data e assina (P8).",
                  "O agente nunca assina."],
    }  # fmt: skip


def zip_name(project: Project, export: Export) -> str:
    if export.kind == "official":
        phase = PHASE_CODES.get(project.phase, "PE")
        return f"{project.code}_{phase}_{SPECIALTY_CODE}_{export.version}.zip"
    return draft_name(project.code, "Conjunto", "zip")


def run_export(db: Session, store: ObjectStore, settings: Settings, publish: Publish,
               export_id: uuid.UUID) -> None:  # fmt: skip
    export = db.get(Export, export_id)
    if export is None:
        return
    project = db.get(Project, export.project_id)
    assert project is not None
    export.status = "running"
    db.commit()
    publish(project.id, _event(export))
    try:
        reasons = refusals(db, project, export.kind)
        if reasons:
            raise ExportRefused(reasons)
        files, contents, problems, notes = build(db, store, settings, export)
        if export.kind == "official" and problems:
            raise ExportRefused(["A verificação de fidelidade falhou: " + "; ".join(problems)])
        data = manifest(db, export, files, problems, notes)
        for f in files:
            f["key"] = f"projects/{project.id}/exports/{export.id}/{f['sha256']}"
            store.put(f["key"], contents[f["name"]], f["media_type"])
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for f in files:
                z.writestr(f["name"], contents[f["name"]])
            z.writestr("manifesto.json", json.dumps(data, ensure_ascii=False, indent=2))
        blob = out.getvalue()
        export.zip_name = zip_name(project, export)
        export.zip_key = f"projects/{project.id}/exports/{export.id}/bundle"
        export.zip_sha256 = hashlib.sha256(blob).hexdigest()
        export.zip_size = len(blob)
        store.put(export.zip_key, blob, "application/zip")
        export.files, export.manifest = files, data
        export.status, export.message = "done", None
    except ExportRefused as exc:
        export.status, export.message = "failed", str(exc)[:2000]
    except Exception as exc:  # noqa: BLE001 - the job must end with a status; details: the log
        logger.error("export %s failed: %s", export.id, type(exc).__name__)
        export.status, export.message = "failed", "A exportação falhou: tente de novo."
    export.finished_at = datetime.now(UTC)
    record(db, None, f"export.{export.status}", "export", export.id,
           {"kind": export.kind, "files": len(export.files), "version": export.version},
           project_id=project.id, actor_type="system")  # fmt: skip
    db.commit()
    publish(project.id, _event(export))
