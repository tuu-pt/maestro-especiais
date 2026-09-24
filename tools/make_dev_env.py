"""Create a local .env from .env.example with random development secrets.

Never overwrites an existing file unless --force is given. Leaves the LLM key
and model names empty: those must come from a TUU Google project.
"""

import argparse
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


def _access_key() -> str:
    return "dev" + "".join(secrets.choice(_ALNUM_LOWER) for _ in range(17))


GENERATED: dict[str, Callable[[], str]] = {
    "POSTGRES_PASSWORD": _token,
    "REDIS_PASSWORD": _token,
    "S3_ACCESS_KEY": _access_key,
    "S3_SECRET_KEY": _token,
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--example", type=Path, default=ROOT / ".env.example")
    parser.add_argument("--output", type=Path, default=ROOT / ".env")
    parser.add_argument("--force", action="store_true", help="overwrite an existing file")
    args = parser.parse_args(argv)

    if args.output.exists() and not args.force:
        print(f"{args.output.name} já existe; nada foi alterado (use --force para substituir).")
        return 0
    args.output.write_text(render(args.example.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"{args.output.name} criado com segredos aleatórios de desenvolvimento.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
