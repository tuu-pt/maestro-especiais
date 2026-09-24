"""Reports. The summary never contains values; only the private detail file does."""

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from anonymizer.detectors import LABELS_PT
from anonymizer.findings import CODES, Finding
from anonymizer.project import ProjectOutcome

MAX_LINES_PER_SECTION = 40

LIMITATION = (
    "Limitação: os nomes de pessoas só são encontrados quando estão nas células e tabelas "
    "conhecidas, em linhas 'Etiqueta: valor', depois de títulos (Eng.º, Arq., Sr.…) ou em "
    "data/private/anonymize_overrides.yaml. Os restantes tipos são procurados por padrão."
)


def _describe(f: Finding) -> str:
    text = CODES[f.code][1]
    if f.kind:
        text = f"{LABELS_PT.get(f.kind, f.kind)} · {text}"
    if f.count > 1:
        text += f" ({f.count})"
    return text


def summary_data(outcomes: list[ProjectOutcome], fixtures_root: Path) -> dict[str, Any]:
    projects = []
    for o in outcomes:
        replaced: Counter[str] = Counter()
        info: Counter[str] = Counter()
        warnings, errors, skipped = [], [], []
        for file in o.files:
            for f in file.findings:
                entry = {
                    "ficheiro": file.output,
                    "onde": f.where,
                    "codigo": f.code,
                    "tipo": f.kind,
                    "contagem": f.count,
                    "descricao": _describe(f),
                }
                if f.code == "replaced":
                    replaced[f.kind or "?"] += f.count
                elif not file.copied:
                    skipped.append(entry)
                elif f.severity == "error":
                    errors.append(entry)
                elif f.severity == "warning":
                    warnings.append(entry)
                else:
                    info[f.code] += f.count
        projects.append(
            {
                "projeto": o.code,
                "promovido": o.promoted,
                # Relative on purpose: absolute paths carry the Windows user name.
                "destino": f"{fixtures_root.name}/{o.code}",
                "ficheiros_anonimizados": sum(1 for f in o.files if f.copied),
                "ficheiros_nao_copiados": sum(1 for f in o.files if not f.copied),
                "substituicoes": dict(sorted(replaced.items())),
                "informacao": dict(sorted(info.items())),
                "avisos": warnings,
                "erros": errors,
                "nao_copiados": skipped,
            }
        )
    return {"gerado_em": datetime.now(UTC).isoformat(timespec="seconds"), "projetos": projects}


def detail_data(outcomes: list[ProjectOutcome]) -> dict[str, Any]:
    """Everything, with values. PRIVATE: written to data/private/ only."""
    return {
        "aviso": "CONTÉM DADOS PESSOAIS. Nunca partilhar nem versionar.",
        "projetos": [
            {
                "projeto": o.code,
                "ficheiros": [
                    {
                        "ficheiro": file.output,
                        "achados": [
                            {
                                "codigo": f.code,
                                "onde": f.where,
                                "tipo": f.kind,
                                "original": f.original,
                                "pseudonimo": f.pseudonym,
                            }
                            for f in file.findings
                        ],
                    }
                    for file in o.files
                ],
            }
            for o in outcomes
        ],
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8"))


def _lines(entries: list[dict[str, Any]]) -> list[str]:
    out = [
        f"    · {e['ficheiro']}" + (f" · {e['onde']}" if e["onde"] else "") + f" · {e['descricao']}"
        for e in entries[:MAX_LINES_PER_SECTION]
    ]
    if len(entries) > MAX_LINES_PER_SECTION:
        out.append(f"    … e mais {len(entries) - MAX_LINES_PER_SECTION} (ver o relatório JSON)")
    return out


def render_summary(data: dict[str, Any]) -> str:
    lines = [
        "Anonimização dos projetos de referência (SPEC 12.2)",
        "Este resumo não tem valores e pode ser partilhado. Os valores ficam só em "
        "data/private/anonymize_detail.json.",
        "",
    ]
    for p in data["projetos"]:
        status = (
            f"OK: {p['destino']} atualizado"
            if p["promovido"]
            else f"FALHOU: {p['destino']} não foi alterado"
        )
        lines.append(f"{p['projeto']} · {status}")
        lines.append(
            f"  Ficheiros: {p['ficheiros_anonimizados']} anonimizados · "
            f"{p['ficheiros_nao_copiados']} não copiados"
        )
        if p["substituicoes"]:
            parts = [f"{LABELS_PT.get(k, k)} {n}" for k, n in p["substituicoes"].items()]
            lines.append("  Substituições: " + " · ".join(parts))
        if p["erros"]:
            lines.append("  Erros (bloqueiam a promoção):")
            lines += _lines(p["erros"])
        if p["avisos"]:
            lines.append("  Revisão obrigatória antes do commit das fixtures:")
            lines += _lines(p["avisos"])
        if p["nao_copiados"]:
            lines.append("  Não copiados:")
            lines += _lines(p["nao_copiados"])
        if p["informacao"]:
            parts = [f"{CODES[k][1]} ({n})" for k, n in p["informacao"].items()]
            lines.append("  Informação: " + " · ".join(parts))
        lines.append("")
    ok = sum(1 for p in data["projetos"] if p["promovido"])
    lines += [LIMITATION, "", f"Resultado: {ok} de {len(data['projetos'])} projetos anonimizados."]
    return "\n".join(lines)
