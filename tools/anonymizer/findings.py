"""What the anonymizer found or did, per file and location. Values stay private."""

from dataclasses import dataclass

SEVERITIES = ("info", "warning", "error")

# code -> (default severity, Portuguese description)
CODES: dict[str, tuple[str, str]] = {
    "replaced": ("info", "substituído"),
    "residual": ("error", "dado pessoal que ficou por substituir"),
    "pii_in_binary": (
        "error",
        "dado pessoal dentro de um objeto binário que não se consegue editar",
    ),
    "unreadable_part": ("error", "parte do ficheiro que não se consegue ler"),
    "internal_error": ("error", "erro interno (ver anonymize_error.log)"),
    "unverifiable": (
        "error",
        "ficheiro que não se consegue verificar: não pode estar nas fixtures",
    ),
    "possible_name": ("warning", "possível nome de pessoa: confirmar"),
    "images_present": ("warning", "imagens: revisão visual obrigatória"),
    "image_not_blanked": ("warning", "imagem de formulário que não foi possível apagar"),
    "binary_not_inspected": ("warning", "objeto embebido não inspecionado por completo"),
    "possible_vector_text": ("warning", "possível texto vetorizado: revisão visual obrigatória"),
    "unknown_fe_version": ("warning", "versão do modelo da ficha eletrotécnica desconhecida"),
    "unreadable": ("warning", "ficheiro ilegível ou corrompido: não foi copiado"),
    "encrypted": ("warning", "ficheiro protegido: não foi copiado"),
    "unsupported": ("info", "formato não suportado: não foi copiado"),
    "thumbnail_removed": ("info", "miniatura da primeira página removida"),
    "images_blanked": ("info", "imagens do formulário apagadas"),
    "image_metadata_removed": ("info", "metadados de imagens removidos"),
    "annotations_removed": ("info", "anotações removidas"),
    "signatures_removed": ("info", "assinaturas digitais removidas"),
    "embedded_files_removed": ("info", "anexos removidos"),
    "metadata_cleared": ("info", "metadados do documento limpos"),
    "formulas_to_values": ("info", "fórmulas convertidas em valores (.xls)"),
}


@dataclass
class Finding:
    code: str
    where: str = ""  # location inside the file (member, cell, paragraph, page); never a value
    kind: str | None = None  # personal-data kind, when relevant
    count: int = 1
    # Sensitive: written only to the private detail file, never printed.
    original: str | None = None
    pseudonym: str | None = None

    @property
    def severity(self) -> str:
        return CODES[self.code][0]


class UnreadableFileError(Exception):
    """A file that cannot be opened (corrupted, encrypted...). It is never copied."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
