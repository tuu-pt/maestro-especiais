from decimal import Decimal

import pytest
from alembic import command
from conftest import alembic_config
from sqlalchemy import Connection, create_engine, inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    Circuit,
    FichaConflict,
    FichaRevision,
    FichaValue,
    Project,
    ProjectFile,
)

TABLES = {
    "project",
    "project_file",
    "ficha_revision",
    "ficha_value",
    "ficha_conflict",
    "circuit",
    "audit_event",
}


def make_project(db: Session, code: str = "R9") -> Project:
    project = Project(code=code, name="Moradia de teste", building_type="moradia unifamiliar")
    db.add(project)
    db.flush()
    return project


def test_migration_goes_down_and_up_again(database_url: str) -> None:
    config = alembic_config(database_url)
    engine = create_engine(database_url)
    try:
        command.downgrade(config, "base")
        assert not TABLES & set(inspect(engine).get_table_names())
        command.upgrade(config, "head")
        assert set(inspect(engine).get_table_names()) >= TABLES
    finally:
        engine.dispose()


def test_full_ficha_graph_round_trips(db: Session) -> None:
    project = make_project(db)
    file = ProjectFile(
        project=project,
        kind="ficha_eletrotecnica",
        filename="FE.xlsm",
        storage_key=f"projects/{project.id}/files/1",
        size_bytes=10,
        checksum="a" * 64,
    )
    revision = FichaRevision(project_id=project.id, label="A")
    db.add_all([file, revision])
    db.flush()
    value = FichaValue(
        revision=revision,
        key="ele.potencia_alimentar_kva",
        group="Alimentação",
        label_pt="Potência a alimentar",
        value=34.5,
        unit="kVA",
        source_type="ficha_eletrotecnica",
        source_ref="Ficha Eletrotecnica!P29",
        source_file_id=file.id,
    )
    circuit = Circuit(
        revision=revision,
        row_index=3,
        origin="Portinhola",
        destination="Q.E.G.",
        kva=Decimal("34.5"),
        i2_a=Decimal("504"),
        iz145_a=Decimal("503.4"),
    )
    db.add_all([value, circuit])
    db.flush()
    db.add(FichaConflict(value_id=value.id, candidates=[{"value": 34.5}, {"value": 41.4}]))
    db.flush()
    db.expire_all()

    loaded = db.scalars(select(FichaRevision).where(FichaRevision.id == revision.id)).one()
    assert loaded.values[0].value == 34.5
    assert loaded.values[0].conflicts[0].candidates[1] == {"value": 41.4}
    assert loaded.circuits[0].iz145_a == Decimal("503.40")


def test_enumerated_columns_are_constrained(db: Session) -> None:
    db.add(Project(code="R8", name="x", phase="obra"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_one_value_per_key_and_revision(db: Session) -> None:
    project = make_project(db)
    revision = FichaRevision(project_id=project.id, label="A")
    db.add(revision)
    db.flush()
    for _ in range(2):
        db.add(
            FichaValue(
                revision_id=revision.id,
                key="id.obra.designacao",
                group="Identificação",
                label_pt="Obra",
                value="x",
                source_type="manual",
            )
        )
    with pytest.raises(IntegrityError):
        db.flush()


def test_same_file_twice_in_a_project_is_rejected(db: Session) -> None:
    project = make_project(db)
    for i in range(2):
        db.add(
            ProjectFile(
                project_id=project.id,
                filename="a.xlsx",
                storage_key=f"k{i}",
                size_bytes=1,
                checksum="b" * 64,
            )
        )
    with pytest.raises(IntegrityError):
        db.flush()


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_event SET action = 'tampered'",
        "DELETE FROM audit_event",
        "TRUNCATE audit_event",
    ],
)
def test_audit_log_is_insert_only(connection: Connection, statement: str) -> None:
    db = Session(bind=connection, join_transaction_mode="create_savepoint")
    db.add(AuditEvent(actor_type="system", action="project.created", entity_type="project"))
    db.flush()

    nested = connection.begin_nested()
    with pytest.raises(DBAPIError, match="insert-only"):
        connection.execute(text(statement))
    nested.rollback()
    assert connection.execute(text("SELECT count(*) FROM audit_event")).scalar() == 1
