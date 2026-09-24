# Maestro Especiais

Agente de IA da TUU para montar, redigir e validar o processo de projeto de instalações elétricas
(MDJ, CTE, MQT/LPU, ficha eletrotécnica, identificação e termo).
Especificação completa: docs/SPEC.md · Mock-up: docs/mockup/maestro-especiais.html

## Regras invioláveis
- O agente não decide: propõe e sinaliza. Correções, conflitos e aprovações exigem ação humana registada.
- O agente não calcula. CAL-01 só compara valores que já estão na Tabela de Cálculo.
- O LLM nunca escreve números, nomes ou valores do projeto: usa {{v:<chave>}} resolvidos pelo backend.
- Dados pessoais (requerente e técnico) nunca são enviados ao LLM nem escritos em logs.
- Blocos fixed são copiados com o OOXML original e nunca passam pelo LLM.
- Só se citam documentos do corpus com citable = true.
- A ficha-base é a fonte de verdade. Fonte mais recente que diverge → propor atualizar a ficha.
- Formulários saem sem data nem assinatura. O agente nunca assina.
- AuditEvent é só de inserção.
- Nunca ler data/private/. Trabalhar só com data/fixtures/ (anonimizado).
  - O Claude Code nunca corre `make anonymize` nem `tools/anonymize.py` sobre data/private/: quem o corre é a equipa, localmente.
  - `.claude/settings.json` bloqueia leitura, escrita e pesquisa em data/private/.

## Convenções
- UI em PT-PT. Código, tabelas, endpoints e commits em inglês.
- Uma tarefa, um commit. Testes sempre junto com o código.
- Frontend: React + TypeScript + Vite. Cores e fontes só via tokens em frontend/src/styles/tokens.css.
- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic.
- Leitores de ficheiros em backend/app/ingest/, um por tipo, com testes sobre as fixtures R1/R2.
- Ficha eletrotécnica: leitura e escrita por células fixas, mapa por versão do modelo DGEG.
- Tabela de Cálculo: colunas detetadas pelo texto do cabeçalho, nunca por posição.
- LLM: Gemini Flash via google-genai, SEMPRE através de LlmProvider em backend/app/llm/.
- Nomes de modelos só em variáveis de ambiente (LLM_MODEL_*).
- Quota gratuita: rate limiting, retry com backoff em 429/503, retoma a meio.
- Saídas do LLM sempre em JSON validado por Pydantic. Prompts em backend/app/llm/prompts/.
- Regras de validação em backend/app/validation/rules/, uma por ficheiro, cada uma com um caso do Anexo C.
- Object storage só pela API S3 genérica (boto3): trocar MinIO por outro S3 é só configuração.

## Comandos
- make setup                 # .venv + dependências Python + npm ci + Chromium do Playwright
- make env                   # gera .env local com segredos aleatórios de desenvolvimento
- docker compose up          # ambiente completo
- make test                  # pytest + vitest
- make lint                  # ruff + mypy + eslint + tsc
- make e2e                   # Playwright
- make anonymize             # corre tools/anonymize.py (local, fora do Git)
- make pii-check             # procura padrões de dados pessoais em data/fixtures/ (também na CI)
- Sem make (Windows): `winget install ezwinports.make`

## Dados
- data/fixtures/ : R1 e R2 anonimizados (versionados)
- data/private/  : originais, tabela de correspondências, relatórios detalhados e overrides (NUNCA versionar)

## Decisões tomadas
Seguem a recomendação da secção 16 da SPEC enquanto a equipa não decidir o contrário.

| # | Decisão | Estado |
|---|---|---|
| D1 | Backend Python (FastAPI) | Recomendação seguida |
| D2 | PostgreSQL 16 + pgvector | Recomendação seguida |
| D3 | Embeddings Gemini | ✅ Decidido |
| D4 | Alojamento cloud na UE | Recomendação seguida; por agora só ambiente local |
| D5 | Termos da Gemini API | **Pendente (direção).** Até lá nenhum dado real vai ao LLM; só fixtures anonimizadas |
| D6 | Autenticação Entra ID, se aplicável | A decidir na Fase 2 (TI) |
| D7 | Curador | A designar (coordenação) |
| D8 | Esqueletos da secção 8.3 | Seguidos tal como estão, a validar com os técnicos |
| D9 | Integração TUU Maestro | Endpoint de exportação no MVP |
| D10 | Gemini Flash | ✅ Decidido |
| D11 | MVP em eletricidade | ✅ Decidido |
| D12 | Leitura de DWG | Adiada |
| D13 | Severidade da CAL-01 | Aviso |

Stack (secção 6): a recomendada. Versões fixadas em backend/pyproject.toml, tools/requirements.txt e frontend/package-lock.json.

Decisões da Fase 0:
- React 18.3 (como na SPEC, embora a 19 seja a atual) e TypeScript 6.0 (o TS 7 nativo ainda não é suportado pelo typescript-eslint).
- MinIO fixado na última imagem oficial, só para desenvolvimento (a edição comunitária está em manutenção).
- Anonimização:
  - PyMuPDF (AGPL-3.0) só em tools/, nunca no backend (que usa pdfplumber).
  - `.xls` reescritos só com valores (as fórmulas passam a valores).
  - Pseudonimizar só dados pessoais: empresas, câmaras, designação da obra, concelho, freguesia e distrito ficam reais.
  - Tabela de pseudónimos global (R1 e R2) e injetiva: valores reais diferentes dão pseudónimos diferentes, para que C3 e C7 continuem detetáveis.
  - Mapa de células da ficha eletrotécnica (FE_v.20190222) em tools/anonymizer/maps/ [A CONFIRMAR com o modelo DGEG vazio].

## Estado atual
- Fase: 0 (em curso)
