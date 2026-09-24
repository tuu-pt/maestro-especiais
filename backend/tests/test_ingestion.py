import asyncio
import logging
import uuid
from typing import Any

import factories
import fakeredis
import pytest
from conftest import Api, Published, RecordingQueue
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest import pipeline
from app.ingest.pipeline import ReaderError
from app.models import AuditEvent, ProjectFile
from app.progress import channel, project_events

FE = factories.ficha_eletrotecnica()


def new_project(api: Api) -> str:
    response = api.as_("redator").post("/api/projects", json={"code": "R9", "name": "Moradia"})
    return str(response.json()["id"])


def upload(api: Api, project_id: str, data: bytes = FE, name: str = "FE.xlsm") -> dict[str, Any]:
    response = api.as_("redator").post(
        f"/api/projects/{project_id}/files", files={"file": (name, data)}
    )
    body: dict[str, Any] = response.json()
    return body


@pytest.fixture
def processor(monkeypatch: pytest.MonkeyPatch) -> list[bytes]:
    """A stand-in reader for the ficha eletrotécnica that records what it read."""
    seen: list[bytes] = []

    def read(db: Session, file: ProjectFile, data: bytes) -> str:
        seen.append(data)
        return "3 valores lidos"

    monkeypatch.setitem(pipeline.PROCESSORS, "ficha_eletrotecnica", read)
    return seen


def test_upload_queues_the_file_and_announces_it(
    api: Api, queue: RecordingQueue, published: Published
) -> None:
    body = upload(api, new_project(api))

    assert body["job_id"] == "job-1"
    assert queue.enqueued == [uuid.UUID(body["file"]["id"])]
    assert published[-1][1]["step"] == "Ficheiro carregado"
    assert published.statuses() == ["pending"]


def test_files_without_reader_are_not_queued(api: Api, queue: RecordingQueue) -> None:
    body = upload(api, new_project(api), factories.PDF_MINIMAL, "EL.pdf")
    assert body["job_id"] is None and queue.enqueued == []


def test_unavailable_queue_keeps_the_file_with_a_message(api: Api, queue: RecordingQueue) -> None:
    queue.available = False
    body = upload(api, new_project(api))

    assert body["job_id"] is None
    assert body["file"]["ingest_status"] == "pending"
    assert "indisponível" in body["file"]["ingest_message"]


@pytest.mark.usefixtures("inline_ingestion")
def test_ingestion_runs_the_reader_and_reports_each_step(
    api: Api, published: Published, processor: list[bytes], db: Session
) -> None:
    body = upload(api, new_project(api))
    file = db.get(ProjectFile, uuid.UUID(body["file"]["id"]))

    assert processor == [FE]  # read back from the object store
    assert file is not None and file.ingest_status == "done"
    assert file.ingest_message == "3 valores lidos"
    # running and done from the worker, then the upload's own announcement
    assert published.statuses() == ["running", "done", "done"]
    assert "file.ingested" in db.scalars(select(AuditEvent.action)).all()


@pytest.mark.usefixtures("inline_ingestion")
def test_reader_failure_is_reported_without_values(
    api: Api,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    published: Published,
) -> None:
    def broken(db: Session, file: ProjectFile, data: bytes) -> str:
        raise ValueError("NIF 234567899 inválido")

    monkeypatch.setitem(pipeline.PROCESSORS, "ficha_eletrotecnica", broken)
    caplog.set_level(logging.DEBUG)

    body = upload(api, new_project(api))
    file = db.get(ProjectFile, uuid.UUID(body["file"]["id"]))

    assert file is not None and file.ingest_status == "failed"
    assert file.ingest_message == "Não foi possível ler o ficheiro (ValueError)."
    assert "234567899" not in caplog.text
    assert all("234567899" not in str(event) for _, event in published)
    assert "file.ingest_failed" in db.scalars(select(AuditEvent.action)).all()


@pytest.mark.usefixtures("inline_ingestion")
def test_reader_errors_explain_themselves(
    api: Api, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unknown_version(db: Session, file: ProjectFile, data: bytes) -> str:
        raise ReaderError("Versão do modelo DGEG desconhecida: é preciso um novo mapa de células.")

    monkeypatch.setitem(pipeline.PROCESSORS, "ficha_eletrotecnica", unknown_version)
    body = upload(api, new_project(api))
    file = db.get(ProjectFile, uuid.UUID(body["file"]["id"]))

    assert file is not None and file.ingest_status == "failed"
    assert file.ingest_message is not None and "novo mapa" in file.ingest_message


def test_events_endpoint_requires_a_user(api: Api) -> None:
    project_id = new_project(api)
    assert api.as_(None).get(f"/api/projects/{project_id}/events").status_code == 401


def test_event_stream_sends_the_current_state_then_live_updates() -> None:
    server = fakeredis.FakeServer()
    project_id = uuid.uuid4()
    initial: list[dict[str, Any]] = [{"file_id": "a", "status": "done"}]

    async def scenario() -> list[dict[str, str]]:
        client = fakeredis.FakeAsyncRedis(server=server)
        stream = project_events(client, project_id, initial)
        received = [await anext(stream)]
        waiting = asyncio.ensure_future(anext(stream))
        await asyncio.sleep(0.05)  # let the subscription settle
        fakeredis.FakeRedis(server=server).publish(
            channel(project_id), '{"file_id": "b", "status": "running"}'
        )
        received.append(await asyncio.wait_for(waiting, timeout=2))
        await stream.aclose()
        await client.aclose()
        return received

    received = asyncio.run(scenario())
    assert [m["event"] for m in received] == ["file", "file"]
    assert '"a"' in received[0]["data"] and '"running"' in received[1]["data"]
