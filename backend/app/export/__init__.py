"""Export of the pieces of a project (SPEC 8.5, 10.H, 11; Phase 6).

The official export needs every condition of app.review and the approval of the técnico
responsável; until then only a draft, with the watermark "RASCUNHO — não aprovado" on every page
and in the file name, never with the official naming convention.
"""

from dataclasses import dataclass

WATERMARK = "RASCUNHO — não aprovado"
DRAFT_SUFFIX = "RASCUNHO-nao-aprovado"
# Phase of the project in the TUU file names [A CONFIRMAR]: PE (execução), PL (licenciamento)
PHASE_CODES = {"execucao": "PE", "licenciamento": "PL"}
SPECIALTY_CODE = "ELE"
TITLES = {"MDJ": "Memória Descritiva e Justificativa", "CTE": "Condições Técnicas Especiais"}
SUBJECTS = {"execucao": "Projeto de execução de eletricidade",
            "licenciamento": "Projeto de licenciamento de eletricidade"}  # fmt: skip


class ExportRefused(Exception):
    """The official export is not possible yet: the reasons are for people."""

    def __init__(self, reasons: list[str]) -> None:
        super().__init__(" ".join(reasons))
        self.reasons = reasons


@dataclass(frozen=True)
class Exported:
    name: str
    data: bytes
    media_type: str


def official_name(code: str, piece: str, phase: str, version: str, ext: str) -> str:
    """<CÓDIGO>_<PEÇA>_<FASE>_ELE_V<n>.<ext> (SPEC 10.H)."""
    return f"{code}_{piece}_{PHASE_CODES.get(phase, 'PE')}_{SPECIALTY_CODE}_{version}.{ext}"


def draft_name(code: str, piece: str, ext: str) -> str:
    return f"{code}_{piece}_{DRAFT_SUFFIX}.{ext}"
