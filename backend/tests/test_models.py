from decimal import Decimal

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from conftest import alembic_config
from sqlalchemy import Connection, create_engine, inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.db import Base
from app.ingest.consolidate import draft_revision
from app.models import (
    AuditEvent,
    BomItem,
    Circuit,
    CircuitSheet,
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
    "circuit_sheet",
    "bom_item",
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


def _describe(diff: object) -> str:
    item = diff[0] if isinstance(diff, list) else diff  # modify_* come as a list of tuples
    assert isinstance(item, tuple)
    op, *rest = item
    names = [str(getattr(r, "name", r)) for r in rest if isinstance(r, str | object)][:3]
    return f"{op} {' '.join(names)}"


def test_migrations_match_the_models(connection: Connection) -> None:
    context = MigrationContext.configure(connection, opts={"compare_type": True})
    diffs = [_describe(d) for d in compare_metadata(context, Base.metadata)]
    # Indexes are declared in the migrations only (a convention of this project).
    assert [d for d in diffs if not d.startswith("remove_index ")] == []


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


# ---------------------------------------------------------------- Phase 2: 09-Folhas, MQT/LPU


def revision_with_circuit(db: Session) -> tuple[FichaRevision, Circuit]:
    project = make_project(db)
    revision = FichaRevision(project_id=project.id, label="A")
    db.add(revision)
    db.flush()
    circuit = Circuit(revision_id=revision.id, row_index=12, origin="Portinhola", destination="QE")
    db.add(circuit)
    db.flush()
    return revision, circuit


def test_a_conflict_is_on_a_value_or_on_a_circuit_field(db: Session) -> None:
    _, circuit = revision_with_circuit(db)
    db.add(FichaConflict(circuit_id=circuit.id, field="in_a", candidates=[{"value": 250}]))
    db.flush()
    assert circuit.conflicts[0].field == "in_a"


@pytest.mark.parametrize(
    "kwargs",
    [{}, {"field": "in_a"}, {"with_circuit": True}],
    ids=["none", "field only", "no field"],
)
def test_a_conflict_needs_exactly_one_target(db: Session, kwargs: dict[str, object]) -> None:
    _, circuit = revision_with_circuit(db)
    circuit_id = circuit.id if kwargs.pop("with_circuit", False) else None
    db.add(FichaConflict(circuit_id=circuit_id, candidates=[], **kwargs))
    with pytest.raises(IntegrityError):
        db.flush()


def test_a_new_revision_copies_sheets_and_bom_items_with_their_links(db: Session) -> None:
    revision, circuit = revision_with_circuit(db)
    db.add_all(
        [
            CircuitSheet(
                revision_id=revision.id, origin_hint="Port", destination_hint="QE",
                template="TUU_09", values={"in_a": {"value": 50, "ref": "proteccao!E9"}},
                circuit_ids=[str(circuit.id)], link_status="rule",
            ),
            BomItem(
                revision_id=revision.id, variant="mqt", row_index=27, source_ref="MQT!linha 27",
                code="8.2.1.1", level=4, kind="article", designation="Q.E.G", unit="un",
                quantity=Decimal("1"), link_key="ele.quadros", link_status="rule",
                link_rule="board",
            ),
        ]
    )  # fmt: skip
    revision.status = "confirmed"
    db.flush()
    db.refresh(revision)

    new = draft_revision(db, revision.project_id, "dev:tecnico")

    assert new.label == "B"
    sheet = new.circuit_sheets[0]
    assert sheet.circuit_ids == [str(new.circuits[0].id)] != [str(circuit.id)]
    assert sheet.values["in_a"]["ref"] == "proteccao!E9" and sheet.link_status == "rule"
    item = new.bom_items[0]
    assert (item.code, item.link_key, item.quantity) == ("8.2.1.1", "ele.quadros", Decimal("1"))
