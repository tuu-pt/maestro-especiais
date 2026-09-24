# Fixtures

Projetos de referência **anonimizados** por `tools/anonymize.py` (secção 12.2 da SPEC).

- `R1/`: moradia unifamiliar, projeto de execução de eletricidade.
- `R2/`: reabilitação de biblioteca municipal, projeto de execução de eletricidade com FV, VE, SADI, KNX, UPS e audiovisual.

Regras:

- Só entram aqui ficheiros gerados pelo anonimizador, depois de `make pii-check` limpo e de revisão visual dos avisos do relatório.
- Nunca copiar ficheiros de `data/private/` à mão.
- Os pseudónimos têm formatos reservados (ex.: NIF `99999xxxx` com dígito de controlo inválido, emails `@example.com`, códigos postais `0000-nnn`) para que a CI os reconheça sem a tabela de correspondências.
