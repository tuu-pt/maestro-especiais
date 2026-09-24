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
- A aplicação começa vazia: tudo o que aparece nos ecrãs vem dos documentos carregados. Nunca dados
  fictícios na interface; cada ecrã tem um estado vazio que explica o que falta e a ação seguinte
  (SPEC 10). O mock-up serve para o layout, os estados e as interações, não para o conteúdo.
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
- Object storage só pela API S3 genérica (boto3): trocar de servidor S3 é só configuração.

Decisões da Fase 1 (confirmam-se com R1/R2 anonimizados):
- Dados pessoais visíveis para todos os papéis, mascarados por omissão ("•••") na API e na interface; revelar é explícito e fica na auditoria.
- CAL-01 só com IB ≤ In ≤ Iz e I2 ≤ 1,45·Iz; queda de tensão e poder de corte esperam pela MDJ (a interface diz porquê).
- Fontes locais com @fontsource-variable; React Router 7 (a 8 exige React 19).
- Mapa de células da ficha eletrotécnica em backend/app/ingest/maps/fe_v20190222.yaml: **confirmado** em 24 set 2026 pelas
  etiquetas do modelo DGEG nas fichas anonimizadas de R1 e R2 (a ordem da SPEC 7.2 estava errada a partir de C8);
  R45 desconhecida → para com aviso.
- Tabela de Cálculo: colunas por sinónimos do cabeçalho, com a 2.ª linha de cabeçalho do modelo TUU (sob "TIPO C");
  linhas de secção não são troços; colunas desconhecidas geram aviso. Potência do troço = "TOTAL INSTALADO" [A CONFIRMAR]
  (em R1 e R2 é igual a "Norma [kVA]", sem socorro nem segurança).
- Comparação entre fontes: 1.ª linha da Tabela (potência) ↔ `ele.potencia_alimentar_kva` (confirmado com C6 e o controlo de R1);
  fases da 1.ª linha ↔ entrada.
- Revisões: a ingestão escreve na revisão em rascunho; depois de confirmada abre-se a seguinte; a mesma fonte substitui o seu candidato; confirmar exige zero conflitos e o papel técnico.
- Autenticação de desenvolvimento: 4 utilizadores (redator, técnico, curador, admin) pelo cabeçalho X-Dev-User, só com DEV_AUTH=true; o OIDC (D6) substitui só esta dependência.
- S3: chave `projects/<uuid>/files/<uuid>` (o nome original só na BD); SHA-256 e deduplicação por projeto.
- Tokens: `--ink-3` escurecido (claro #66645c, escuro #99958a) para contraste AA; o mock-up tem #77746b/#8e8a80.

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
- S3 de desenvolvimento: SeaweedFS 4.47 (Apache 2.0), serviço `s3` no Docker Compose. Substituiu o MinIO em 24 set 2026,
  quando as imagens públicas do MinIO deixaram de estar disponíveis (a CI falhava no download). Só a API S3 fica
  exposta no host; as interfaces web do SeaweedFS não têm autenticação.
- Anonimização:
  - PyMuPDF (AGPL-3.0) só em tools/, nunca no backend (que usa pdfplumber).
  - `.xls` reescritos só com valores (as fórmulas passam a valores).
  - Pseudonimizar só dados pessoais: empresas, câmaras, designação da obra, concelho, freguesia e distrito ficam reais.
  - Tabela de pseudónimos global (R1 e R2) e injetiva: valores reais diferentes dão pseudónimos diferentes, para que C3 e C7 continuem detetáveis.
  - Mapa de células da ficha eletrotécnica (FE_v.20190222) em tools/anonymizer/maps/: confirmado em 24 set 2026 (como o do leitor).
  - Emails **não** são anonimizados (decisão do utilizador, 24 set 2026, contra a recomendação da SPEC 12.2 e com o aviso
    sobre o P9): continuam detetados, mas não são substituídos nem verificados (`KEPT_KINDS` em tools/anonymizer/engine.py).
    Consequência: os emails do requerente e do técnico ficam nas fixtures (repositório privado). Tudo o que for enviado
    ao LLM a partir das fixtures (Fase 3 em diante) tem de passar os emails por placeholder.
  - Nomes da equipa TUU **não** são dados pessoais nas fixtures (decisão do utilizador, 24 set 2026): um nome de um
    engenheiro ficou em 12 ficheiros de R1/R2 (carimbaduras "NOME | ENG ELETROTÉCNICO", formulários, MQT/LPU) e aceita-se;
    o histórico do Git fica como está. Também passam por placeholder no que for enviado ao LLM.

## Estado atual
- Fase: 1 **fechada** (24 set 2026). Fases 0 e 1 concluídas; próxima: Fase 2.
- Feito na Fase 1:
  - backend: modelos Project, ProjectFile, FichaRevision, FichaValue, FichaConflict, Circuit e AuditEvent
    (insert-only por trigger) com Alembic; projetos, upload para S3 com checksum e tipo detetado,
    ficha-base, revelar, resolver conflitos, confirmar, auditoria e atividade; worker RQ com SSE;
  - leitores sem LLM da ficha eletrotécnica (mapa confirmado com R1/R2) e da Tabela de Cálculo (modelo TUU
    com cabeçalho em duas linhas), consolidação com FichaConflict, CAL-01;
  - frontend: ecrãs A–H com estados vazios e sem dados inventados; ecrã C com dados reais;
  - fixtures R1 e R2 anonimizadas e versionadas (55 ficheiros, `make pii-check` limpo, revisão visual feita).
- Verificado no fecho: pytest 279 (inclui a aceitação de R1/R2: controlo de potência de R1 sem conflitos,
  C6 como FichaConflict, C10 na CAL-01), Vitest 26, Playwright 48 (estados vazios, axe WCAG 2.1 AA nos dois
  temas, 400 px, teclado) e o percurso com R2 contra a stack real (criar → carregar → resolver o conflito de
  potência → confirmar → auditoria), com capturas claro/escuro/telemóvel.
- [A CONFIRMAR] pela equipa:
  - potência de cada troço da Tabela = "TOTAL INSTALADO" (em R1/R2 igual a "Norma [kVA]");
  - fixtures: em R1 a freguesia foi substituída por um pseudónimo de morada (mapa antigo do anonimizador);
    uma nova execução do anonimizador, já com o mapa corrigido, deixa-a real.
- Percurso com R2: `make up` e depois `RUN_R2_JOURNEY=1 npm run e2e` (cria um projeto na BD de desenvolvimento;
  repor com `docker compose down -v`).
- Notas de ambiente:
  - `make test` exige o Docker a correr (Postgres do compose);
  - o worker usa o código montado (PYTHONPATH=/srv/backend); o backend também (uvicorn);
  - o Vite no contentor não recarrega alterações no Windows, mesmo com polling: reiniciar o contentor
    frontend; o Playwright usa o seu próprio servidor na porta 5174;
  - o teste de integração do worker (RUN_INGEST_E2E) cria dados na BD de desenvolvimento: só na CI;
  - Docker Desktop no Windows: com o Resource Saver, o motor para ao fim de ~5 min sem contentores;
    se o arranque falhar com `sailor-ingest.sock`, reiniciar o Docker Desktop.
- Anonimizador, notas de funcionamento:
  - objetos OLE e VBA: são pesquisados os valores conhecidos; se houver dados, falha; se não houver, fica aviso de revisão visual;
  - os emails ficam como estão (KEPT_KINDS); os restantes tipos são substituídos em todos os ficheiros e projetos;
  - imagens nos formulários são apagadas, as restantes geram aviso; as miniaturas da primeira página são removidas;
  - páginas PDF com muito vetor e pouco texto (fontes SHX) geram aviso de revisão visual;
  - dados que o script não encontra sozinho (nomes soltos, falsos positivos): data/private/anonymize_overrides.yaml (ver README).
- Próximo: Fase 2 (leitores das 09-Folhas, MQT/LPU e PDF das peças desenhadas, ligados à ficha-base com origem
  e conflitos). D6 (Entra ID) a decidir com a TI na Fase 2.
