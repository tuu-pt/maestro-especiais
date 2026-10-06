"""Create a local .env from .env.example with random development secrets.

Never overwrites an existing file unless --force is given; --add-missing only appends the
variables of .env.example the file does not have yet (existing values are never read out).
Leaves the LLM key and model names empty: those must come from a TUU Google project.
"""

import argparse
import base64
import secrets
import string
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_ALNUM_LOWER = string.ascii_lowercase + string.digits


def _token(length: int = 32) -> str:
    # URL-safe characters only, so the values can go straight into connection URLs.
    return secrets.token_urlsafe(length)


def _fernet_key() -> str:
    """A key for cryptography.fernet: 32 random bytes, URL-safe base64."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def _access_key() -> str:
    return "dev" + "".join(secrets.choice(_ALNUM_LOWER) for _ in range(17))


GENERATED: dict[str, Callable[[], str]] = {
    "POSTGRES_PASSWORD": _token,
    "REDIS_PASSWORD": _token,
    "S3_ACCESS_KEY": _access_key,
    "S3_SECRET_KEY": _token,
    "PROFILE_ENCRYPTION_KEY": _fernet_key,
    "EXPORT_LINK_SECRET": _token,
    "MAESTRO_SERVICE_TOKEN": _token,
}

DEFAULTS: dict[str, str] = {
    "POSTGRES_USER": "maestro",
    "POSTGRES_DB": "maestro_especiais",
    "S3_BUCKET": "maestro-especiais",
    "LLM_PROVIDER": "gemini",
    "EMBEDDING_DIM": "768",
}


def render(example: str) -> str:
    lines = []
    for line in example.splitlines():
        key, sep, value = line.partition("=")
        key = key.strip()
        if sep and not line.lstrip().startswith("#") and not value.strip():
            if key in GENERATED:
                line = f"{key}={GENERATED[key]()}"
            elif key in DEFAULTS:
                line = f"{key}={DEFAULTS[key]}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def missing(example: str, current: str) -> str:
    """The lines of the rendered example whose variable the current file does not define."""
    defined = {line.partition("=")[0].strip() for line in current.splitlines() if "=" in line}
    new = [line for line in render(example).splitlines()
           if "=" in line and not line.lstrip().startswith("#")
           and line.partition("=")[0].strip() not in defined]  # fmt: skip
    return "".join(f"{line}\n" for line in new)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--example", type=Path, default=ROOT / ".env.example")
    parser.add_argument("--output", type=Path, default=ROOT / ".env")
    parser.add_argument("--force", action="store_true", help="overwrite an existing file")
    parser.add_argument("--add-missing", action="store_true",
                        help="append the variables the existing file does not have")  # fmt: skip
    args = parser.parse_args(argv)

    if args.add_missing and args.output.exists():
        current = args.output.read_text(encoding="utf-8")
        new = missing(args.example.read_text(encoding="utf-8"), current)
        if new:
            sep = "" if current.endswith("\n") or not current else "\n"
            args.output.write_bytes((current + sep + new).encode("utf-8"))
        names = [line.partition("=")[0] for line in new.splitlines()]
        print(f"Acrescentadas: {', '.join(names)}." if names else "Nada a acrescentar.")
        return 0

    if args.output.exists() and not args.force:
        print(f"{args.output.name} já existe; nada foi alterado (use --force para substituir).")
        return 0
    # LF only: docker compose would otherwise keep a trailing \r in every value.
    content = render(args.example.read_text(encoding="utf-8"))
    args.output.write_bytes(content.encode("utf-8"))
    print(f"{args.output.name} criado com segredos aleatórios de desenvolvimento.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
