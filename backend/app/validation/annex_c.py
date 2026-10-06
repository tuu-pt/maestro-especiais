"""The cases of Annex C (SPEC) and the report of how the validation finds them (Phase 5).

    make anexo-c-report  →  docs/fase5-anexo-c.md

The report is written by the acceptance test (backend/tests/test_validation_annex_c.py), from
R1 and R2 loaded as audits in the test database: it says, for each case, the rule, whether it
was found, the likely reading obtained and the evidence (masked), then the controls, the other
real alerts and the rules with no case in Annex C. It never shows a personal value.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

# (rule, words that must all be in the message)
Match = tuple[str, tuple[str, ...]]
Issue = dict[str, Any]


@dataclass(frozen=True)
class Case:
    id: str
    project: str  # R1, R2, or R1-CCP (R1 marked as public procurement)
    what: str
    expected: str | None  # the likely reading of Annex C (None: "—")
    matches: tuple[Match, ...]  # every one must be found
    reading_of: int = 0  # which match gives the reading compared with `expected`


CASES = (
    Case("C1", "R1", "MDJ indica fios H07V-K; CTE e Tabela de Cálculo indicam H07V-U",
         "Erro provável na MDJ", (("COE-06", ("MDJ (existente) indica H07V-K",)),)),
    Case("C2", "R1", "CTE (videoporteiro): «ecrã na entrada de cada apartamento» numa moradia",
         "Texto herdado de outro projeto", (("TIP-01", ("«apartamento»", "Videoporteiro")),)),
    Case("C3", "R1", "N.º de membro OET do técnico diferente entre MDJ/CTE e identificação/termo",
         "Confirmar com o perfil do técnico", (("COE-04", ("n.º de membro OET",)),)),
    Case("C4", "R1", "Índice das peças desenhadas com 17 folhas; PDF com 16 páginas",
         "Folha em falta no PDF ou índice desatualizado", (("DES-01", ("17 folhas",)),)),
    Case("C5", "R1-CCP", "Videoporteiro com marca sem «ou equivalente»; referência repetida",
         None, (("CCP-01", ("Videoporteiro",)), ("TXT-01", ("«45070 S»",)))),
    Case("C6", "R2", "Potência: ficha eletrotécnica 180 kVA; CTE e Tabela 200 kVA; MDJ sem valor",
         "Erro provável na ficha eletrotécnica",
         (("COE-05", ("Ficha eletrotécnica 180 kVA",)),
          ("CNT-01", ("MDJ (existente): não indica a potência",)))),
    Case("C7", "R2", "Ficha eletrotécnica com outro requerente, «Escritório», rua e freguesia "
         "vazias", "Ficha reaproveitada de outro projeto",
         (("COE-04", ("(requerente)", "Ficha eletrotécnica")), ("TIP-01", ("«Escritório»",)))),
    Case("C8", "R2", "Carregadores VE: MDJ e Tabela 5; CTE 3 pedestais com 2 carregadores (6)",
         "Erro provável no CTE", (("COE-01", ("carregadores", "CTE (existente) 6")),)),
    Case("C9", "R2", "Cabos: FXZ1 (MDJ/CTE), RZ1-K (AS) (Tabela), XZ1(frt,zh) (LPU)",
         "Pedir equivalência ao curador",
         (("COE-06", ("indica FXZ1",)), ("COE-06", ("LPU indica XZ1(frt,zh)",)))),
    Case("C10", "R2", "Troço Portinhola → Q.E.G.: I2 = 504 A e 1,45·Iz = 503,4 A",
         "Confirmar na folha de cálculo", (("CAL-01", ("Portinhola → Q.E.G.", "I2 = 504 A")),)),
    Case("C11", "R2", "«Segundo a secção das RTIEBT» e «secções da RTIEBT» sem número", None,
         (("REF-03", ("«secção das RTIEBT»",)), ("REF-03", ("«secções da RTIEBT»",)))),
    Case("C12", "R2", "Troços enterrados (ENT) e MDJ sem bloco de canalizações enterradas",
         "Bloco em falta na MDJ", (("COE-03", ("MDJ (existente)", "Canalizações Enterradas")),)),
    Case("C13", "R2", "Parágrafos da MDJ com quebras de linha a meio de frase", None,
         (("TXT-01", ("MDJ (existente)", "quebra de linha a meio de frase")),)),
    Case("C14", "R1", "Duas entradas quase iguais sobre normas portuguesas na legislação da MDJ",
         None, (("TXT-01", ("quase iguais", "Normas portuguesas")),)),
)  # fmt: skip

# Controls of Annex C: none of these may be found
CONTROLS = (
    ("R1", "Potência (34,5 kVA) igual na ficha eletrotécnica, identificação, MDJ e Tabela",
     "COE-05", ()),
    ("R1", "N.º de quadros (6) igual na MDJ, CTE, MQT e Tabela", "COE-01", ("quadros",)),
)  # fmt: skip

WITHOUT_CASE = {
    "REF-01": "texto do agente com fonte fora do corpus (tests/test_validation_engine.py) e "
    "citações do texto fora do corpus (aparecem em R2 como «outros alertas»)",
    "REF-02": "documento revogado (tests/test_validation_rules.py) e documentos por confirmar "
    "pelo curador (informação, em R1 e R2)",
    "NUM-01": "número fora de marcador no texto do agente (tests/test_validation_engine.py)",
    "COE-02": "ficheiro com data posterior à ficha-base (tests/test_validation_rules.py)",
    "EQP-01": "equipamento do CTE montado contra a ficha técnica "
    "(tests/test_validation_equipment.py); R1 e R2 entram aqui como peças existentes",
    "EQP-02": "ficha técnica com mais de 3 anos (tests/test_validation_equipment.py)",
    "EQP-03": "equipamento sem ficha técnica (tests/test_validation_equipment.py)",
}


def find(
    issues: Iterable[dict[str, Any]], rule: str, words: tuple[str, ...]
) -> list[dict[str, Any]]:
    return [i for i in issues if i["rule_id"] == rule and all(w in i["message"] for w in words)]


@dataclass
class Result:
    case: Case
    found: list[dict[str, Any] | None]

    @property
    def detected(self) -> bool:
        return all(self.found)

    @property
    def reading(self) -> str | None:
        issue = self.found[self.case.reading_of] if self.found else None
        return issue["likely_reading"] if issue else None

    @property
    def reading_ok(self) -> bool:
        if self.case.expected is None:
            return True
        return bool(self.reading) and _same_reading(self.reading or "", self.case.expected)


def _same_reading(obtained: str, expected: str) -> bool:
    """«Ficha eletrotécnica reaproveitada de outro projeto (…)» is «Ficha reaproveitada…»."""

    def plain(text: str) -> str:
        return text.lower().replace("ficha eletrotécnica", "ficha").rstrip(".")

    return plain(obtained).startswith(plain(expected))


def evaluate(states: dict[str, dict[str, Any]]) -> list[Result]:
    results = []
    for case in CASES:
        issues = states[case.project]["issues"]
        found: list[Issue | None] = [next(iter(find(issues, rule, words)), None)
                                     for rule, words in case.matches]  # fmt: skip
        results.append(Result(case, found))
    return results


def control_alerts(states: dict[str, dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    return [(what, find(states[p]["issues"], rule, words)) for p, what, rule, words in CONTROLS]


def _evidence(issue: dict[str, Any]) -> str:
    e = issue.get("evidence") or {}
    if e.get("excerpt"):
        return f"«{e['excerpt']}»"
    values = e.get("values") or []
    if isinstance(values, dict):  # CAL-01: the values of the circuit, by name
        return "; ".join(f"{k} = {v}" for k, v in values.items())
    if values:
        shown = [f"{v['piece_name']}: {v['value']}{' ≠' if v.get('differs') else ''}"
                 for v in values[:6]]  # fmt: skip
        ref = e.get("reference") or {}
        head = f"{ref['label']}: {ref['value']} · " if isinstance(ref, dict) and ref else ""
        return head + "; ".join(shown)
    parts = [f"{k}: {v}" for k, v in e.items()
             if isinstance(v, str | int | float) and k not in ("masked",)][:4]  # fmt: skip
    return "; ".join(parts)


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def markdown(states: dict[str, dict[str, Any]]) -> str:
    results = evaluate(states)
    ok = sum(r.detected and r.reading_ok for r in results)
    out = [
        "# Fase 5 · Anexo C: os casos reais de R1 e R2 na validação",
        "",
        "Gerado por `make anexo-c-report` (`app/validation/annex_c.py`, a partir do teste "
        "`tests/test_validation_annex_c.py`): R1 e R2 carregados como auditoria (ficha "
        "eletrotécnica, Tabela de Cálculo, MQT/LPU, PDF das peças desenhadas e a MDJ, o CTE, a "
        "identificação e o termo feitos à mão), ficha-base confirmada como no projeto aprovado e "
        "validação corrida. Não mostra valores pessoais: a evidência sai mascarada (•••).",
        "",
        f"**{ok} de {len(results)} casos detetados com a leitura provável esperada.**",
        "",
        "| Caso | Projeto | O que acontece | Regra | Resultado | Leitura obtida | Evidência |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        rules = " + ".join(dict.fromkeys(rule for rule, _ in r.case.matches))
        result = ("Detetado" if r.detected else "**Não detetado**") + (
            "" if r.reading_ok else " (leitura diferente)")  # fmt: skip
        evidence = " · ".join(_evidence(i) for i in r.found if i)
        project = "R1 (contratação pública)" if r.case.project == "R1-CCP" else r.case.project
        out.append(f"| {r.case.id} | {project} | {_cell(r.case.what)} | {rules} | {result} | "
                   f"{_cell(r.reading or '—')} | {_cell(evidence)} |")  # fmt: skip
    out += ["", "## Casos de controlo (não podem gerar alertas)", "",
            "| Controlo | Alertas |", "|---|---|"]  # fmt: skip
    for what, alerts in control_alerts(states):
        out.append(f"| {_cell(what)} | {len(alerts) or 'nenhum'} |")
    out += ["", "## Outros alertas reais", "",
            "Alertas que a validação encontra em R1 e R2 para além do Anexo C, para a equipa "
            "rever (a leitura provável é a da regra). Os de informação estão contados, não "
            "listados.", ""]  # fmt: skip
    matched = {id(i) for r in results for i in r.found if i}
    for code in ("R1", "R2"):
        others = [i for i in states[code]["issues"]
                  if id(i) not in matched and i["severity"] != "info"]  # fmt: skip
        info = sum(1 for i in states[code]["issues"] if i["severity"] == "info")
        out += [f"### {code} ({len(others)} críticos e avisos; {info} de informação)", "",
                "| Regra | Severidade | Alerta | Leitura |", "|---|---|---|---|"]  # fmt: skip
        for i in others:
            severity = {"critical": "Crítico", "warning": "Aviso"}[i["severity"]]
            out.append(f"| {i['rule_id']} | {severity} | {_cell(i['message'])} | "
                       f"{_cell(i['likely_reading'] or '—')} |")  # fmt: skip
        out.append("")
    out += ["## Regras sem caso no Anexo C", "", "| Regra | Coberta por |", "|---|---|"]
    out += [f"| {rule} | {_cell(how)} |" for rule, how in WITHOUT_CASE.items()]
    out += [""]
    return "\n".join(out)
