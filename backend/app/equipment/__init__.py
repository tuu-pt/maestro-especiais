"""Equipment library (Phase 7): categories, parameters, seeding from the CTE, datasheets."""

# id -> label (PT), and the words of a CTE block key that make a block about that category
CATEGORIES: dict[str, str] = {
    "portinhola": "Portinhola",
    "quadro": "Quadro elétrico",
    "tubo": "Tubo",
    "caixa": "Caixa",
    "aparelhagem": "Aparelhagem (interruptores e tomadas)",
    "espelho": "Espelho",
    "detetor": "Detetor de movimento",
    "luminaria": "Luminária",
    "iluminacao_seguranca": "Iluminação de segurança",
    "videoporteiro": "Videoporteiro",
    "knx": "KNX",
    "estrutura_fv": "Estrutura fotovoltaica",
    "modulo_fv": "Módulo fotovoltaico",
    "inversor": "Inversor",
    "contador": "Contador de energia",
    "sadi": "SADI",
    "carregador_ve": "Carregador de veículos elétricos",
    "audiovisual": "Audiovisual",
    "terra": "Terras e elétrodos",
}

BLOCK_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("entrada_de_energia", "portinhola"),
    ("quadros_eletricos", "quadro"),
    ("tubos", "tubo"),
    ("caixa_de_visita", "terra"),
    ("caixas", "caixa"),
    ("aparelhagem", "aparelhagem"),
    ("interruptores", "aparelhagem"),
    ("espelhos", "espelho"),
    ("detetores", "detetor"),
    ("iluminacao_normal", "luminaria"),
    ("iluminacao_seguranca", "iluminacao_seguranca"),
    ("videoporteiro", "videoporteiro"),
    ("knx", "knx"),
    ("estrutura", "estrutura_fv"),
    ("modulos_fotovoltaicos", "modulo_fv"),
    ("inversor", "inversor"),
    ("contador", "contador"),
    ("sadi", "sadi"),
    ("veiculos_eletricos", "carregador_ve"),
    ("video", "audiovisual"),
    ("conferencia", "audiovisual"),
    ("palco", "audiovisual"),
    ("controlo_e_automacao", "audiovisual"),
    ("eletrodos", "terra"),
)


def block_category(block_key: str) -> str | None:
    """The category of the equipment a CTE block is about (None: not an equipment block)."""
    if ".condicoes_tecnicas_especiais." not in block_key and not block_key.startswith(
        "condicoes_tecnicas_especiais."
    ):
        return None
    tail = block_key.rsplit(".", 1)[-1]
    return next((c for word, c in BLOCK_CATEGORIES if word in tail), None)
