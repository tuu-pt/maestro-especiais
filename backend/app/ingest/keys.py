"""Stable keys of the ficha-base (SPEC 7.2): group, Portuguese label, unit and personal flag."""

from dataclasses import dataclass


@dataclass(frozen=True)
class KeyInfo:
    group: str
    label_pt: str
    unit: str | None = None
    personal: bool = False
    numeric: bool = False


GROUPS = (
    "Identificação",
    "Imóvel",
    "Alimentação",
    "Distribuição",
    "Sistemas",
    "Equipamentos",
    "Peças desenhadas",
)

KEYS: dict[str, KeyInfo] = {
    # Identificação
    "id.requerente.nome": KeyInfo("Identificação", "Requerente", personal=True),
    "id.requerente.nif": KeyInfo("Identificação", "NIF do requerente", personal=True),
    "id.requerente.morada": KeyInfo("Identificação", "Morada do requerente", personal=True),
    "id.requerente.email": KeyInfo("Identificação", "Email do requerente", personal=True),
    "id.requerente.cp": KeyInfo("Identificação", "Código postal do requerente", personal=True),
    "id.obra.designacao": KeyInfo("Identificação", "Designação da obra"),
    "id.local.rua": KeyInfo("Identificação", "Rua", personal=True),
    "id.local.cp": KeyInfo("Identificação", "Código postal"),
    "id.local.freguesia": KeyInfo("Identificação", "Freguesia"),
    "id.local.concelho": KeyInfo("Identificação", "Concelho"),
    "id.local.distrito": KeyInfo("Identificação", "Distrito"),
    "id.local.gps": KeyInfo("Identificação", "Coordenadas", personal=True),
    "id.local.nip": KeyInfo("Identificação", "NIP"),
    # Imóvel
    "ele.descricao_imovel": KeyInfo("Imóvel", "Descrição do imóvel"),
    "ele.classificacao": KeyInfo("Imóvel", "Classificação do local"),
    "ele.tipo_utilizacao": KeyInfo("Imóvel", "Tipo de utilização"),
    "ele.instalacao": KeyInfo("Imóvel", "Instalação"),
    # Alimentação
    "ele.tipo_instalacao": KeyInfo("Alimentação", "Tipo de instalação"),
    "ele.entrada": KeyInfo("Alimentação", "Entrada"),
    "ele.potencia_instalada_kva": KeyInfo("Alimentação", "Potência instalada", "kVA", numeric=True),
    "ele.fator_simultaneidade": KeyInfo("Alimentação", "Fator de simultaneidade", numeric=True),
    "ele.potencia_alimentar_kva": KeyInfo(
        "Alimentação", "Potência a alimentar", "kVA", numeric=True
    ),
    "ele.potencia_existente_kva": KeyInfo("Alimentação", "Potência existente", "kVA", numeric=True),
    "ele.n_ramais": KeyInfo("Alimentação", "N.º de ramais", numeric=True),
    "ele.tensao_resp_kv": KeyInfo("Alimentação", "Tensão da RESP", "kV", numeric=True),
    "ele.contagem": KeyInfo("Alimentação", "Contagem"),
    # Distribuição (Tabela de Cálculo)
    "ele.quadros": KeyInfo("Distribuição", "Quadros"),
    "ele.cabos": KeyInfo("Distribuição", "Cabos"),
}


def info(key: str) -> KeyInfo:
    try:
        return KEYS[key]
    except KeyError:
        raise KeyError(f"unknown ficha-base key: {key}") from None
