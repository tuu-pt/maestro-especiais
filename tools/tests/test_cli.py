import json
from pathlib import Path

import anonymize
import docx
import openpyxl
import pytest
import synthetic as s


@pytest.fixture
def roots(tmp_path: Path) -> tuple[Path, Path]:
    private, fixtures = tmp_path / "private", tmp_path / "fixtures"
    s.full_project(private / "R9")
    return private, fixtures


def cli(private: Path, fixtures: Path, *args: str) -> int:
    return anonymize.main([*args, "--private-root", str(private), "--fixtures-root", str(fixtures)])


def fe_cells(fixtures: Path, code: str) -> tuple[str, str]:
    ws = openpyxl.load_workbook(next((fixtures / code).glob("FE_*.xlsm"))).active
    assert ws is not None
    return str(ws["C5"].value), str(ws["C11"].value)


# ---------------------------------------------------------------- happy path


def test_run_writes_fixtures_table_and_reports_in_the_right_places(
    roots: tuple[Path, Path],
) -> None:
    private, fixtures = roots

    assert cli(private, fixtures, "R9") == 0

    assert (fixtures / "R9").is_dir()
    table = json.loads((private / anonymize.MAP_FILE).read_text(encoding="utf-8"))
    assert table["version"] == 1 and table["entries"]["name"]
    assert (private / anonymize.REPORT_FILE).exists()
    assert (private / anonymize.DETAIL_FILE).exists()
    leaked = [p.name for p in fixtures.rglob("*") if "map" in p.name or "detail" in p.name]
    assert leaked == []
    assert not (private / ".staging" / "R9").exists()


def test_console_and_summary_never_show_values(
    roots: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    private, fixtures = roots
    cli(private, fixtures, "R9")
    out = capsys.readouterr()
    printed = out.out + out.err
    summary = (private / anonymize.REPORT_FILE).read_text(encoding="utf-8")

    for text in (printed, summary):
        assert s.find_pii(text) == []
        assert "@example.com" not in text and "99999" not in text  # nor pseudonyms
    assert "R9 · OK: fixtures/R9 atualizado" in printed
    assert str(fixtures) not in printed  # absolute paths carry the Windows user name
    assert "Revisão obrigatória" in printed and "texto vetorizado" in printed
    assert "formato não suportado" in printed


def test_detail_file_is_the_only_place_with_values(roots: tuple[Path, Path]) -> None:
    private, fixtures = roots
    cli(private, fixtures, "R9")
    detail = (private / anonymize.DETAIL_FILE).read_text(encoding="utf-8")

    assert "Maria Sousa Ferreira" in detail
    assert "CONTÉM DADOS PESSOAIS" in detail


def test_same_person_same_pseudonym_across_projects_different_requerente_c7(
    roots: tuple[Path, Path],
) -> None:
    private, fixtures = roots
    s.ooxml_project(private / "R8", other_requerente=True)

    assert cli(private, fixtures, "R9", "R8") == 0

    requerente_r9, tecnico_r9 = fe_cells(fixtures, "R9")
    requerente_r8, tecnico_r8 = fe_cells(fixtures, "R8")
    assert tecnico_r9 == tecnico_r8
    assert requerente_r9 != requerente_r8


def test_second_run_gives_identical_pseudonyms(roots: tuple[Path, Path]) -> None:
    private, fixtures = roots

    def identification() -> list[str]:
        path = next((fixtures / "R9").glob("Identificacao_*.docx"))
        return [c.text for t in docx.Document(str(path)).tables for r in t.rows for c in r.cells]

    cli(private, fixtures, "R9")
    first = identification()
    counters = json.loads((private / anonymize.MAP_FILE).read_text())["counters"]
    cli(private, fixtures, "R9")

    assert identification() == first
    assert json.loads((private / anonymize.MAP_FILE).read_text())["counters"] == counters


# ---------------------------------------------------------------- failures


def test_value_that_cannot_be_substituted_fails_the_run(
    roots: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import anonymizer.engine as engine
    from anonymizer.pseudonyms import render as real

    monkeypatch.setattr(
        engine, "render", lambda kind, value, n: value if kind == "nif" else real(kind, value, n)
    )
    private, fixtures = roots

    assert cli(private, fixtures, "R9") == 1

    assert not (fixtures / "R9").exists()
    printed = capsys.readouterr().out
    assert "FALHOU" in printed and "NIF" in printed
    assert s.find_pii(printed) == []


def test_pii_in_an_embedded_object_fails_the_run(roots: tuple[Path, Path]) -> None:
    private, fixtures = roots
    s.add_ole_with_pii(private / "R9" / "R9_MDJ_PE_ELE_V0.docx")

    assert cli(private, fixtures, "R9") == 1
    assert not (fixtures / "R9").exists()


@pytest.mark.parametrize(
    "args",
    [[], ["../R9"], ["R7"]],
    ids=["no project", "path traversal", "missing folder"],
)
def test_usage_errors(roots: tuple[Path, Path], args: list[str]) -> None:
    private, fixtures = roots
    assert cli(private, fixtures, *args) == 2


def test_empty_project_folder_is_a_usage_error(roots: tuple[Path, Path]) -> None:
    private, fixtures = roots
    (private / "R8" / "vazia").mkdir(parents=True)

    assert cli(private, fixtures, "R8") == 2
    assert not (fixtures / "R8").exists()


def test_project_with_nothing_to_anonymize_is_not_promoted(
    roots: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    private, fixtures = roots
    (private / "R8").mkdir()
    (private / "R8" / "originais.rar").write_bytes(b"Rar!\x1a\x07\x00")

    assert cli(private, fixtures, "R8") == 1
    assert not (fixtures / "R8").exists()
    printed = capsys.readouterr().out
    assert "R8 · FALHOU" in printed and "0 anonimizados · 1 não copiados" in printed


def test_fixtures_inside_the_private_root_are_refused(roots: tuple[Path, Path]) -> None:
    private, _ = roots
    assert cli(private, private / "fixtures", "R9") == 2


def test_private_root_inside_the_repository_must_be_git_ignored(tmp_path: Path) -> None:
    not_ignored = anonymize.ROOT / "tools"
    assert anonymize._git_ignored(not_ignored) is False
    assert anonymize._git_ignored(anonymize.ROOT / "data" / "private") is True
    assert anonymize._git_ignored(tmp_path) is None


# ---------------------------------------------------------------- --check (CI)


def test_check_passes_on_anonymized_fixtures(roots: tuple[Path, Path]) -> None:
    private, fixtures = roots
    cli(private, fixtures, "R9")

    assert anonymize.main(["--check", str(fixtures)]) == 0


def test_check_catches_a_real_value_without_the_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixtures = tmp_path / "fixtures" / "R9"
    fixtures.mkdir(parents=True)
    d = docx.Document()
    d.add_paragraph(f"NIF {s.PROMOTOR.nif}, telefone {s.PROMOTOR.phone}")
    d.save(str(fixtures / "copiado_a_mao.docx"))

    assert anonymize.main(["--check", str(tmp_path / "fixtures")]) == 1
    out = capsys.readouterr().out
    assert "FALHOU" in out and s.find_pii(out) == []


def test_check_rejects_files_it_cannot_verify(tmp_path: Path) -> None:
    fixtures = tmp_path / "fixtures" / "R9"
    fixtures.mkdir(parents=True)
    (fixtures / "planta.dwg").write_bytes(b"AC1032")

    assert anonymize.main(["--check", str(tmp_path / "fixtures")]) == 1


def test_confirmed_false_positive_passes_the_check_through_hashes(tmp_path: Path) -> None:
    private, fixtures = tmp_path / "private", tmp_path / "fixtures"
    project = private / "R9"
    project.mkdir(parents=True)
    d = docx.Document()
    d.add_paragraph("A vala segue pelo Largo do Moinho Velho até ao quadro.")
    d.save(str(project / "Nota.docx"))
    (private / anonymize.OVERRIDES_FILE).write_text(
        "allow:\n  - {kind: address, value: Largo do Moinho Velho}\n", encoding="utf-8"
    )

    assert cli(private, fixtures, "R9") == 0
    allowlist = (fixtures / "R9" / ".pii-allowlist.json").read_text()
    assert "Moinho" not in allowlist  # hashes only
    assert anonymize.main(["--check", str(fixtures)]) == 0
    (fixtures / "R9" / ".pii-allowlist.json").unlink()
    assert anonymize.main(["--check", str(fixtures)]) == 1
