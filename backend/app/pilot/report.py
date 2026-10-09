"""docs/fase8-piloto.md: the pilot's numbers for the team (`make pilot-report`).

Only the project code, the typology, times, counts and the problems written during the pilot.
Never the project name, addresses, people or values of the ficha. The problems are written by
people: the privacy patterns are masked, and a problem that names a personal value of the
project, a technician or a blocked name is left out with a note saying so.
"""

import sys
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.library import privacy
from app.llm.guard import PrivacyGuard, terms_for
from app.models import PilotNote
from app.pilot.metrics import (
    GOAL_REDUCTION,
    GROUPS,
    ProjectMetrics,
    pilot_projects,
    project_metrics,
)
from app.pilot.steps import GOAL_STEPS
from app.profiles import personal_terms

LEFT_OUT = "(texto omitido: tinha um dado pessoal do projeto ou de uma pessoa)"


def minutes(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    return f"{seconds / 60:.0f} min" if seconds < 5400 else f"{seconds / 3600:.1f} h"


def percent(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.0f} %"


def safe_text(db: Session, note: PilotNote, people: list[tuple[str, str]]) -> str:
    guard = PrivacyGuard(terms_for(db, note.project_id) + people)
    text = privacy.mask(note.text)
    if guard.check({"note": text}):
        return LEFT_OUT
    return " ".join(text.split())


def _project(m: ProjectMetrics, notes: list[str]) -> list[str]:
    lines = [f"## {m.code}" + (f" · {m.typology}" if m.typology else ""), ""]
    lines += ["| Passo | Na aplicação | Processo manual (estimativa) |", "|---|---|---|"]
    for r in m.steps:
        estimate = f"{r.estimate[0]}\u2013{r.estimate[1]} min" if r.estimate else "—"
        lines.append(f"| {r.label} | {minutes(r.seconds)} | {estimate} |")
    data = m.as_json()
    lines.append(f"| **Total** | **{minutes(data['seconds'])}** | "
                 f"**{minutes(data['estimate_seconds'])}** (meio do intervalo) |")  # fmt: skip
    goal = m.goal
    lines += ["", f"- Redução no total (passos com estimativa): {percent(m.reduction())}.",
              f"- Redução na MDJ, no CTE e nos formulários (meta ≥ {GOAL_REDUCTION:.0%}): "
              f"{percent(goal['reduction'])}."]  # fmt: skip
    if m.rounds_estimate is not None:
        lines.append(f"- Voltas de correção habituais (estimativa): {m.rounds_estimate}.")
    if not m.approvals:
        lines.append("- Ainda nenhuma peça aprovada: as incoerências contam-se na aprovação.")
    else:
        lines += ["", "| Peça | Rev. | " + " | ".join(lbl for _, lbl in GROUPS.values()) + " |",
                  "|---|---|" + "---|" * len(GROUPS)]  # fmt: skip
        for a in m.approvals:
            cells = [f"{g['found']} encontradas, {g['open']} abertas, {g['ignored']} ignoradas"
                     for g in a.groups.values()]  # fmt: skip
            lines.append(f"| {a.document} | {a.revision} | " + " | ".join(cells) + " |")
    verdict = "**cumprida**" if goal["met"] else "por cumprir"
    lines += [
        "",
        f"Meta do piloto neste projeto: {verdict} (tempo "
        f"{'✓' if goal['time_ok'] else '✗'}, coerência {'✓' if goal['coherent'] else '✗'}).",
    ]
    if notes:
        lines += ["", f"Problemas registados ({len(notes)}):", ""] + [f"- {n}" for n in notes]
    return [*lines, ""]


def render(db: Session, today: datetime | None = None) -> str:
    when = (today or datetime.now(UTC)).date().isoformat()
    projects = pilot_projects(db)
    lines = ["# Fase 8 · Piloto", "",
             f"Gerado por `make pilot-report` em {when}. Só números, o código de cada projeto e os "
             "problemas registados (com os dados pessoais omitidos).", "",
             f"Meta (SPEC 1): reduzir pelo menos {GOAL_REDUCTION:.0%} do tempo de "
             f"{', '.join(GOAL_STEPS)} e zero incoerências de identificação, potência e cabos nas "
             "peças aprovadas. O tempo na aplicação é o tempo ativo medido por ecrã (sem pausas "
             "de mais de 2 minutos); o tempo fora da aplicação não conta.", ""]  # fmt: skip
    if not projects:
        return "\n".join([*lines, "Ainda não há projetos com tempo medido ou estimativa.", ""])
    people = personal_terms(db, get_settings())  # the technicians' profiles
    summary = [project_metrics(db, p) for p in projects]
    met = sum(1 for m in summary if m.goal["met"])
    lines += [f"Projetos: {len(summary)} · meta cumprida em {met}.", ""]
    for m in summary:
        notes = db.scalars(select(PilotNote).where(PilotNote.project_id == m.project_id)
                           .order_by(PilotNote.created_at)).all()  # fmt: skip
        lines += _project(m, [f"[{n.step or n.screen or '—'}] {safe_text(db, n, people)}"
                              + (" (resolvido)" if n.status == "resolved" else "")
                              for n in notes])  # fmt: skip
    loose = db.scalars(select(PilotNote).where(PilotNote.project_id.is_(None))
                       .order_by(PilotNote.created_at)).all()  # fmt: skip
    if loose:
        lines += ["## Problemas sem projeto", ""]
        lines += [f"- [{n.screen or '—'}] {safe_text(db, n, people)}" for n in loose] + [""]
    return "\n".join(lines)


def main() -> int:
    from app.db import get_session

    db = next(get_session())
    try:
        sys.stdout.buffer.write(render(db).encode("utf-8"))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
