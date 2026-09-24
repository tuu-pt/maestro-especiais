from pathlib import Path

import make_dev_env

EXAMPLE = """# comment=kept
POSTGRES_USER=
POSTGRES_PASSWORD=
S3_ACCESS_KEY=
S3_SECRET_KEY=
REDIS_PASSWORD=
GEMINI_API_KEY=
LLM_MODEL_DRAFTING=
DB_HOST_PORT=
"""


def _parse(text: str) -> dict[str, str]:
    return dict(
        line.split("=", 1) for line in text.splitlines() if line and not line.startswith("#")
    )


def _run(tmp_path: Path, *extra: str) -> Path:
    example = tmp_path / ".env.example"
    example.write_text(EXAMPLE, encoding="utf-8")
    output = tmp_path / ".env"
    make_dev_env.main(["--example", str(example), "--output", str(output), *extra])
    return output


def test_generates_random_secrets_and_defaults(tmp_path: Path) -> None:
    values = _parse(_run(tmp_path).read_text(encoding="utf-8"))

    assert values["POSTGRES_USER"] == "maestro"
    for key in ("POSTGRES_PASSWORD", "S3_SECRET_KEY", "REDIS_PASSWORD"):
        assert len(values[key]) >= 32
    assert len(values["S3_ACCESS_KEY"]) >= 16


def test_leaves_llm_key_models_and_ports_empty(tmp_path: Path) -> None:
    values = _parse(_run(tmp_path).read_text(encoding="utf-8"))

    assert values["GEMINI_API_KEY"] == ""
    assert values["LLM_MODEL_DRAFTING"] == ""
    assert values["DB_HOST_PORT"] == ""


def test_secrets_differ_between_runs(tmp_path: Path) -> None:
    first = _parse(_run(tmp_path).read_text(encoding="utf-8"))
    second = _parse(_run(tmp_path, "--force").read_text(encoding="utf-8"))

    assert first["POSTGRES_PASSWORD"] != second["POSTGRES_PASSWORD"]


def test_never_overwrites_existing_env_without_force(tmp_path: Path) -> None:
    output = tmp_path / ".env"
    output.write_text("POSTGRES_PASSWORD=mine\n", encoding="utf-8")

    _run(tmp_path)

    assert output.read_text(encoding="utf-8") == "POSTGRES_PASSWORD=mine\n"


def test_writes_lf_line_endings(tmp_path: Path) -> None:
    assert b"\r" not in _run(tmp_path).read_bytes()


def test_secrets_are_url_safe(tmp_path: Path) -> None:
    values = _parse(_run(tmp_path).read_text(encoding="utf-8"))
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")

    for key in ("POSTGRES_PASSWORD", "REDIS_PASSWORD", "S3_ACCESS_KEY", "S3_SECRET_KEY"):
        assert set(values[key]) <= allowed
