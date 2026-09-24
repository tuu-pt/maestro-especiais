"""Anonymize the reference projects (SPEC 12.2).

    python tools/anonymize.py R1 R2             data/private/<P>/ -> data/fixtures/<P>/
    python tools/anonymize.py --check data/fixtures

Runs locally only. The correspondence table, the detailed report (with values) and
the error log stay in data/private/. The console never shows personal data.
Exit codes: 0 clean · 1 personal data left or not verifiable · 2 usage error.
"""

import argparse
import re
import subprocess
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from anonymizer.check import check_tree, render_check
from anonymizer.project import Overrides, ProjectOutcome, run_project
from anonymizer.pseudonyms import PseudonymMap
from anonymizer.report import detail_data, render_summary, summary_data, write_json

ROOT = Path(__file__).resolve().parents[1]
MAP_FILE = "anonymization_map.json"
OVERRIDES_FILE = "anonymize_overrides.yaml"
REPORT_FILE = "anonymize_report.json"
DETAIL_FILE = "anonymize_detail.json"
ERROR_LOG = "anonymize_error.log"
_CODE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


class UsageError(Exception):
    pass


def _inside(path: Path, folder: Path) -> bool:
    return path == folder or folder in path.parents


def _git_ignored(path: Path) -> bool | None:
    """True/False when path is inside this Git repository, None otherwise."""
    if not _inside(path, ROOT):
        return None
    probe = path / "probe.docx"
    try:
        done = subprocess.run(
            ["git", "-C", str(ROOT), "check-ignore", "-q", str(probe)],
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    return done.returncode == 0


def _validate(private_root: Path, fixtures_root: Path, projects: list[str]) -> None:
    if not projects:
        raise UsageError("indique pelo menos um projeto (ex.: R1 R2) ou use --check")
    for code in projects:
        if not _CODE.match(code):
            raise UsageError(f"código de projeto inválido: {code!r}")
        if not (private_root / code).is_dir():
            raise UsageError(f"não existe a pasta do projeto {code} na raiz privada")
        if not any(p.is_file() for p in (private_root / code).rglob("*")):
            raise UsageError(f"a pasta do projeto {code} não tem ficheiros")
    if _inside(fixtures_root, private_root) or _inside(private_root, fixtures_root):
        raise UsageError("a raiz privada e a raiz das fixtures não podem estar uma dentro da outra")
    if _git_ignored(private_root) is False:
        raise UsageError("a raiz privada não está no .gitignore: recuso escrever a tabela aí")


def _anonymize(private_root: Path, fixtures_root: Path, projects: list[str]) -> int:
    map_path = private_root / MAP_FILE
    mapping = PseudonymMap.load(map_path)
    overrides = Overrides.load(private_root / OVERRIDES_FILE)
    outcomes: list[ProjectOutcome] = []
    try:
        for code in projects:
            outcomes.append(
                run_project(
                    code,
                    private_root / code,
                    private_root / ".staging" / code,
                    fixtures_root / code,
                    mapping,
                    overrides,
                    private_root / ERROR_LOG,
                )
            )
    finally:
        mapping.save(map_path)  # keeps pseudonyms stable between runs, even after a failure
    summary = summary_data(outcomes, fixtures_root)
    write_json(private_root / REPORT_FILE, summary)
    write_json(private_root / DETAIL_FILE, detail_data(outcomes))
    print(render_summary(summary))
    return 0 if all(o.promoted for o in outcomes) else 1


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("projects", nargs="*", help="códigos dos projetos (pastas em data/private)")
    parser.add_argument("--check", type=Path, help="só verificar uma pasta de fixtures")
    parser.add_argument("--private-root", type=Path, default=ROOT / "data" / "private")
    parser.add_argument("--fixtures-root", type=Path, default=ROOT / "data" / "fixtures")
    args = parser.parse_args(argv)
    private_root = args.private_root.resolve()
    try:
        if args.check is not None:
            root = args.check.resolve()
            if not root.is_dir():
                raise UsageError(f"a pasta {args.check} não existe")
            result = check_tree(root)
            print(render_check(result, args.check))
            return 1 if result.errors else 0
        fixtures_root = args.fixtures_root.resolve()
        _validate(private_root, fixtures_root, args.projects)
        return _anonymize(private_root, fixtures_root, args.projects)
    except UsageError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - never print the message: it may hold values
        log = private_root / ERROR_LOG
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(traceback.format_exc())
        # Only the file name: absolute paths carry the Windows user name.
        print(f"Erro interno ({type(exc).__name__}). Detalhes em {ERROR_LOG}.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
