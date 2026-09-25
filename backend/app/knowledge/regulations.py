"""Reduced regulation corpus (SPEC 7.5, Annex D): the references found in R1 and R2.

A list of references, not the documents: title, issuer, scope and where the reference projects
cite them. Everything starts "proposed", with no legal status and citable = false: the curator
confirms the edition in force before a document can be cited. Standards under copyright keep
only their title and scope (license_note). Full-text search (RegulationChunk) is future work.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.detect import fold
from app.knowledge.sources import SourceText
from app.library import privacy
from app.models import RegulationDoc

COPYRIGHT_NOTE = "Norma com direitos de autor: guarda-se só o título e o âmbito."


@dataclass(frozen=True)
class Reference:
    code: str
    title: str
    kind: str  # diploma | guia | especificacao | norma
    issuer: str
    scope: str
    pattern: str  # how the reference projects write it (folded text)
    copyrighted: bool = False


CORPUS = (
    Reference("rtiebt", "RTIEBT: Portaria n.º 949-A/2006, na redação atual", "diploma", "Governo",
              "Regras Técnicas das Instalações Elétricas de Baixa Tensão.",
              r"rtiebt|949-a/2006"),
    Reference("dl-96-2017", "Decreto-Lei n.º 96/2017", "diploma", "Governo",
              "Instalações elétricas de serviço particular: termo de responsabilidade e "
              "identificação do projeto.", r"96/2017"),
    Reference("despacho-dgeg-1-2018", "Despacho n.º 1/2018 da DGEG", "diploma", "DGEG",
              "Classificação das instalações usada na ficha eletrotécnica.",
              r"despacho\D{0,12}1/2018"),
    Reference("guia-dgeg-ve", "Guia Técnico das Instalações Elétricas para carregamento de VE",
              "guia", "DGEG", "Instalações de carregamento de veículos elétricos.",
              r"guia tecnico[^.]{0,60}carregamento de (?:ve|veiculos eletricos)\b"),
    Reference("guia-rpc-cabos",
              "Guia Técnico das classes de reação ao fogo dos cabos elétricos (RPC)",
              "guia", "DGEG",
              "Classes de reação ao fogo dos cabos (Regulamento dos Produtos de Construção).",
              r"reacao ao fogo|produtos de construcao"),
    Reference("e-redes-especificacoes", "Especificações da E-REDES (ex.: DMA-C65-210/N)",
              "especificacao", "E-REDES", "Especificações do operador da rede de distribuição, "
              "por exemplo elétrodos de terra.", r"e-redes|dma-c"),
    Reference("np-en-60529", "NP EN 60529", "norma", "IPQ / CENELEC",
              "Graus de proteção dos invólucros (códigos IP).", r"60 ?529", True),
    Reference("np-en-50102", "NP EN 50102", "norma", "IPQ / CENELEC",
              "Graus de proteção contra impactos mecânicos (códigos IK).", r"50 ?102", True),
    Reference("en-60898", "EN 60898", "norma", "CENELEC",
              "Disjuntores para instalações domésticas e análogas.", r"60 ?898", True),
    Reference("np-en-61386", "NP EN 61386", "norma", "IPQ / CENELEC",
              "Sistemas de tubos para instalações elétricas.", r"61 ?386", True),
    Reference("en-50086-2-4", "EN 50086-2-4", "norma", "CENELEC",
              "Sistemas de tubos enterrados.", r"50 ?086", True),
    Reference("en-12464-1", "EN 12464-1", "norma", "CEN",
              "Iluminação de locais de trabalho interiores.", r"12 ?464", True),
    Reference("hd-602-606", "HD 602 / HD 606", "norma", "CENELEC",
              "Comportamento dos cabos em caso de incêndio.", r"\bhd ?60[26]\b", True),
    Reference("portaria-701-h-2008", "Portaria n.º 701-H/2008", "diploma", "Governo",
              "Conteúdo obrigatório dos projetos de obras públicas.", r"701-h/2008"),
)  # fmt: skip


def _found(ref: Reference, texts: Iterable[SourceText]) -> list[dict[str, Any]]:
    pattern = re.compile(ref.pattern)
    found = []
    for t in texts:
        if t.source not in ("MDJ", "CTE", "Formulário"):
            continue
        spaced = " ".join(t.text.split())
        m = pattern.search(fold(spaced))
        if m:
            left, right = max(0, m.start() - 60), min(len(spaced), m.end() + 60)
            snippet = (
                ("…" if left else "") + spaced[left:right] + ("…" if right < len(spaced) else "")
            )
            found.append({"project": t.project, "source": t.source, "file": t.file,
                          "locator": t.locator, "text": privacy.mask(snippet)})  # fmt: skip
    return found


def seed_regulations(db: Session, texts: list[SourceText]) -> int:
    existing = {r.code: r for r in db.scalars(select(RegulationDoc))}
    for ref in CORPUS:
        row = existing.get(ref.code)
        if row is None:
            row = RegulationDoc(code=ref.code, citable=False, review_status="proposed")
            db.add(row)
        found = _found(ref, texts)
        row.found_in = found[:8]
        row.found_count = len(found)
        if row.review_status != "proposed":
            continue  # the curator decided: only the evidence is refreshed
        row.title, row.kind, row.issuer, row.scope = ref.title, ref.kind, ref.issuer, ref.scope
        row.specialties = ["ele"]
        row.copyrighted = ref.copyrighted
        row.license_note = COPYRIGHT_NOTE if ref.copyrighted else None
    db.flush()
    return len(CORPUS)
