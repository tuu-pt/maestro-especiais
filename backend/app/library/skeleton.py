"""Proposed activation rules for the skeleton of SPEC 8.3 (Phase 3), to be approved by the curator.

A block not listed here is always active ("true"): cover, introduction, legislation… (SPEC 8.3).
Each rule is written in the language of app.library.rules and uses only what the ficha-base,
the Tabela de Cálculo and the MQT/LPU already say.

EXPECTED_DIFFERENCES lists where the rules and the reference MDJ do not agree, and why: the tests
check that these are the only differences.
"""

from dataclasses import dataclass

MDJ_RULES: dict[str, str] = {
    # 4. Regulamento dos Produtos de Construção: not in dwellings
    "ele.mdj.regulamento_dos_produtos_de_construcao_rpc":
        'ele.classificacao != "Locais de habitação"',
    # 10. Canalizações enterradas: a buried circuit, or a trench in the MQT/LPU
    "ele.mdj.canalizacoes.canalizacoes_enterradas":
        'any circuit.installation == "ENT" or any bom.designation ~ "abertura e tapamento de vala"',
    # 12. Iluminação de segurança (no reference MDJ has this block: see below)
    "ele.mdj.instalacoes_eletricas_a_considerar.iluminacao_de_seguranca":
        'sys.iluminacao_seguranca.present or any bom.designation ~ "iluminação de segurança"',
    # 13. SADI e matriz de incêndio
    "ele.mdj.sistema_automatico_de_detecao_de_incendio_sadi":
        'any bom.chapter ~ "deteção de incêndio"',
    "ele.mdj.sistema_automatico_de_detecao_de_incendio_sadi.sadi":
        'any bom.chapter ~ "deteção de incêndio"',
    "ele.mdj.sistema_automatico_de_detecao_de_incendio_sadi.matriz_de_incendio":
        'any bom.chapter ~ "deteção de incêndio"',
    # 14. Fotovoltaico · 15. Veículos elétricos (articles linked by the Phase 2 rules)
    "ele.mdj.instalacao_fotovoltaica": "sys.fv.present",
    "ele.mdj.carregamento_de_veiculos_eletricos": "sys.ve.present",
    # 16. Audiovisual
    "ele.mdj.instalacao_audiovisual_auditorio": 'any bom.chapter ~ "audiovisual"',
}  # fmt: skip
ALWAYS = "true"


@dataclass(frozen=True)
class SkeletonBlock:
    """A block of SPEC 8.3 that no reference document has: proposed empty, with its rule."""

    key: str
    title: str
    after: str  # placed after this block
    level: int


SKELETON_ONLY = (
    SkeletonBlock(
        "ele.mdj.instalacoes_eletricas_a_considerar.iluminacao_de_seguranca",
        "Iluminação de Segurança",
        "ele.mdj.instalacoes_eletricas_a_considerar.iluminacao_normal",
        2,
    ),
)

# (block key, project) -> why the rule and the reference MDJ do not agree
EXPECTED_DIFFERENCES: dict[tuple[str, str], str] = {
    ("ele.mdj.canalizacoes.canalizacoes_enterradas", "R2"): (
        "C12: o troço Portinhola → Q.E.G. de R2 é enterrado (ENT) e a MDJ de R2 não tem "
        "canalizações enterradas."
    ),
    ("ele.mdj.instalacao_de_alimentacao_distribuicao_e_medida_de_energia.distribuicao_de_energia",
     "R2"): (
        "O esqueleto 8.3 põe a distribuição sempre; a MDJ de R2 não tem esta secção."
    ),
    ("ele.mdj.instalacoes_eletricas_a_considerar.iluminacao_de_seguranca", "R1"): (
        "O MQT de R1 tem iluminação de segurança e a MDJ de R1 não tem o bloco."
    ),
    ("ele.mdj.instalacoes_eletricas_a_considerar.iluminacao_de_seguranca", "R2"): (
        "A LPU de R2 tem iluminação de segurança (e a MDJ lista-a nas instalações a considerar), "
        "mas não tem o bloco."
    ),
}  # fmt: skip


def rule_for(key: str) -> str:
    return MDJ_RULES.get(key, ALWAYS)
