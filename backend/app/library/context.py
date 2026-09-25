"""What an activation rule sees of a reference project, read from data/fixtures in memory.

The same readers as the ingestion (Phase 1 and 2): the ficha eletrotécnica, the Tabela de Cálculo
and the MQT/LPU, with the article links of the Phase 2 rules.
"""

from pathlib import Path

from app.ingest import bom, tabela_calculo
from app.ingest.bom_links import link_for
from app.ingest.detect import detect
from app.knowledge.sources import unique_files
from app.library.rules import Context
from app.library.seed import ficha_values


def fixture_context(fixtures: Path, code: str) -> Context:
    ctx = Context(values=ficha_values(fixtures, code))
    for path in unique_files(fixtures / code):
        data = path.read_bytes()
        kind = detect(path.name, data).kind
        if kind == "calc_summary":
            ctx.circuits += [dict(c.fields) for c in tabela_calculo.read(data).circuits]
        elif kind in ("mqt", "lpu"):
            chapter = None
            for line in bom.read(data).lines:
                if line.kind == "chapter":
                    chapter = line.designation
                ctx.bom.append({"designation": line.designation, "chapter": chapter,
                                "unit": line.unit})  # fmt: skip
                link = link_for(line.designation)
                if link:
                    ctx.linked.add(link.key)
    return ctx
