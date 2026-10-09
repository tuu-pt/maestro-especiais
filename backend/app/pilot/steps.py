"""The steps of the pilot (Phase 8): the eight asked to the technicians about the manual process.

The frontend says which screen is open and, inside the editor, which part (MDJ, CTE, forms); the
backend turns that into a step. Editing after the project's first review request counts as
«correções» [A CONFIRMAR].
"""

STEPS: dict[str, str] = {
    "dados": "Juntar e conferir os dados de partida",
    "ficha": "Ficha eletrotécnica e ficha-base",
    "mdj": "Escrever a MDJ",
    "cte": "Escrever o CTE",
    "formularios": "Identificação, termo e ficha eletrotécnica",
    "verificacao": "Verificar a coerência entre peças",
    "correcoes": "Corrigir o que a revisão aponta",
    "conjunto": "Montar o conjunto final",
}
# The steps of the SPEC goal: production time of the MDJ, the CTE and the forms (SPEC 1)
GOAL_STEPS = ("mdj", "cte", "formularios")
# Steps that become «correções» once the pieces were sent for review
EDITING = frozenset({"ficha", "mdj", "cte", "formularios"})

SCREENS: dict[str, str] = {
    "ficheiros": "dados",
    "ficha": "ficha",
    "documentos": "mdj",  # the editor: the hint says MDJ, CTE or forms
    "validacao": "verificacao",
    "equipamentos": "verificacao",
    "revisao": "conjunto",
}


def step_for(screen: str, hint: str | None, reviewed: bool) -> str | None:
    """The step of a heartbeat, or None for a screen that is not part of a project's work."""
    # the hint only says which part of the editor (MDJ, CTE, forms) is in use
    step = hint if screen == "documentos" and hint in ("mdj", "cte", "formularios") else None
    step = step or SCREENS.get(screen)
    if step is None:
        return None
    if reviewed and step in EDITING:
        return "correcoes"
    return step
