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

Alojamento na VPS da TUU (compatibilidade, decidido em 25 set 2026):
- As apps da TUU correm numa VPS com Postgres 18.6 (`postgres:18-alpine`), Node 22, Next.js 16.3.4, Debian 12,
  Docker 29.8.0 e Nginx 1.22.1. Por agora o Maestro Especiais fica como está (Postgres 16 + pgvector, Node 24,
  React + Vite, imagens Debian 13), mas **qualquer decisão tem de poder passar para essas versões**:
  - não usar funcionalidades exclusivas de Postgres 16/Node 24/Debian 13 sem avisar; na VPS é preciso pgvector
    (`pgvector/pgvector:…-pg18-bookworm` ou a extensão instalada: a imagem `postgres:18-alpine` não o traz);
  - no Postgres 18 o volume de dados monta em `/var/lib/postgresql` (não em `/var/lib/postgresql/data`);
  - o frontend continua um build estático (Vite) servido pelo Nginx; Next.js não é necessário para isso;
  - atrás do Nginx: `proxy_buffering off` no SSE (`/api/projects/*/events`) e `client_max_body_size` ≥ 200M;
  - configuração só por variáveis de ambiente; S3 genérico.
- A CI tem um job `compat` que o prova em cada push: backend em Postgres 18 + pgvector, frontend em Node 22 e a
  imagem do backend em Debian 12 (`BASE_IMAGE` no Dockerfile).
- A D4 (alojamento cloud na UE) é da direção: alojar na VPS muda-a e tem de ser confirmado (onde está a VPS).

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

Decisões da Fase 2 (25 set 2026):
- 09-Folhas: mapa de células em backend/app/ingest/maps/folha09_tuu.yaml [A CONFIRMAR]; Iz corrigido em proteccao!Z7
  (a SPEC dizia condutores!H52, que é o Iz antes da correção); queda de tensão em fração (× 100).
- A 09-Folha não diz o troço: associa-se pelo nome do ficheiro, com a normalização dos nomes dos quadros
  (backend/app/ingest/boards.py); sem correspondência única fica "por associar" e associa-se à mão.
- Comparação 09-Folha ↔ Tabela à precisão do valor menos preciso (máx. 2 casas) [A CONFIRMAR]; cada diferença é um
  FichaConflict no campo do troço. Em R1, a queda de tensão de Q.E.G. → Q.P.1.2 (0,9 % / 0,76 %) é divergência real.
- MQT e LPU distinguem-se pelo título do documento. Associação de artigos só por regras (quadros, portinhola, VE, FV,
  luminárias pelo código); o resto à mão. Associação assistida por LLM: trabalho futuro (SPEC 8.2).
- "Câmara Municipal de X" = "Município de X" na comparação (regra explícita em consolidate.entity).
- PDF das peças desenhadas com pypdfium2 (BSD/Apache), não pdfplumber (~12 s por página em R2). Só índice,
  carimbadura e n.º de páginas; a legenda fica para mais tarde. A ficha mostra índice ≠ folhas (C4); DES-01 é da Fase 5.
- Avisos da leitura em project_file.ingest_warnings, à parte do resumo.
- Nas fixtures de R1, os campos pessoais da carimbadura saem baralhados (efeito do anonimizador): os testes de R1 só usam
  os campos não pessoais da carimbadura.

Decisões da Fase 3 (25 set 2026; aprovadas pelo utilizador, o resto [A CONFIRMAR] pelo curador):
- Sem LLM nem embeddings. O corpus é uma lista de referências; a pesquisa no texto integral fica para mais tarde (SPEC 7.5).
- Regras de ativação: linguagem de texto curta, parser próprio (backend/app/library/rules.py), texto + árvore JSON; sem eval.
- OOXML: fragmento por secção (SourceSection) + pacote por documento de origem no S3 (SourceDocument); media por SHA-256.
- Adaptativos: o texto de cada projeto vai para ArchiveDoc/ArchiveChunk (com marcadores); o bloco guarda regra e referências.
- Capa e assinatura: chaves novas `doc.local`, `doc.data`, `tec.*`, resolvidas na Fase 4 (`doc.data` vazio, P8).
- Nenhum bloco guarda dados de um projeto ou de uma pessoa: teste de fuga em backend/tests/test_library_blocks.py.
- [A CONFIRMAR] modo do bloco = o mais forte dos parágrafos; placeholder só com a mesma chave em R1 e R2, ou `single_source`
  quando o parágrafo só existe num projeto; tabelas e imagens nunca adaptativas; condições técnicas gerais do CTE fixas;
  valores trocados: `id.*`, potências (kVA), tensão (kV), capa e assinatura pelas etiquetas; valores das listas DGEG ficam
  como texto; equivalências de cabos só com evidência (mesma secção, fontes diferentes), nunca -U com -K;
  RegulationDoc com `review_status` e `citable` só com o documento confirmado e em vigor; `record()` com `project_id=None`
  nos eventos da biblioteca; o cabeçalho (técnico, data, revisão) fica no pacote e terá de ser paramétrico na Fase 4.
- Tudo o que o curador tem de rever: docs/revisao-curador.md (gerado por `make curator-review`).

## Comandos
- make setup                 # .venv + dependências Python + npm ci + Chromium do Playwright
- make env                   # gera .env local com segredos aleatórios de desenvolvimento
- docker compose up          # ambiente completo
- make test                  # pytest + vitest
- make lint                  # ruff + mypy + eslint + tsc
- make e2e                   # Playwright
- make anonymize             # corre tools/anonymize.py (local, fora do Git)
- make pii-check             # procura padrões de dados pessoais em data/fixtures/ (também na CI)
- make seed-library          # propostas da biblioteca e do conhecimento a partir de data/fixtures (idempotente)
- make curator-review        # escreve docs/revisao-curador.md a partir das propostas
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
| D6 | Autenticação Entra ID, se aplicável | Por decidir com a TI (não decidida na Fase 2; o login de desenvolvimento continua) |
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
  - PyMuPDF (AGPL-3.0) só em tools/, nunca no backend (que usa pypdfium2).
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
- Fase: 3 **implementada** (25 set 2026), à espera do curador (D7): a fase fecha quando os blocos estiverem aprovados.
  Fases 0, 1 e 2 concluídas.
- Feito na Fase 3:
  - dicionário de cabos (designações tal como aparecem e onde, equivalências propostas com evidência) e léxico de
    tipologias (termos incompatíveis com a evidência, C2), migração 0005;
  - MDJ/CTE de R1/R2 partidos em secções com o OOXML original e ida e volta verificada (0006); 95 blocos propostos
    (42 MDJ, 53 CTE) com evidência, marcadores e arquivo (0007, 0008); regras de ativação para o esqueleto 8.3;
    `equipment_slots` no CTE; corpus reduzido do Anexo D, só referências, nada citável (0009);
  - ecrã G: dicionário, léxico, biblioteca (evidência lado a lado, pré-visualização, aprovar/editar/rejeitar, histórico)
    e corpus; decisões só do papel Curador, na auditoria.
- Verificado: pytest 500 (backend 334 + anonimizador 166; inclui a ida e volta dos quatro .docx, IP/IK fixas, potência de
  R1 paramétrica, assinatura sem dados do técnico, teste de fuga, regras sobre R1/R2), Vitest 45, Playwright 66 + os
  percursos com a stack real (R2 das Fases 1 e 2; curador da Fase 3), `make pii-check` limpo.
- [A CONFIRMAR] pela equipa:
  - Fase 3: as decisões de método acima e cada proposta em docs/revisao-curador.md;
  - mapa de células das 09-Folhas (maps/folha09_tuu.yaml) e a regra de comparação à precisão do menos preciso;
  - potência de cada troço da Tabela = "TOTAL INSTALADO" (em R1/R2 igual a "Norma [kVA]");
  - secção do troço lida da designação do cabo (Circuit.section_mm2);
  - em R2 a LPU lista 16 quadros e a Tabela 14 (Q.SEGURANÇA, Q.DESENF, "Q.UPS" vs "Q.UPS 10kVA"): conflito real a rever;
- Biblioteca: `make up`, `make seed-library` (lê só data/fixtures, montada só para leitura no contentor do backend) e
  `make curator-review`. Percurso do curador: `RUN_CURATOR_JOURNEY=1 npm run e2e` (aprova um bloco na BD de
  desenvolvimento; repor com `docker compose down -v` e voltar a semear).
- Percursos com R2: `make up` e depois `RUN_R2_JOURNEY=1 npm run e2e` (criam projetos na BD de desenvolvimento;
  repor com `docker compose down -v`). Depois de mudar dependências do backend: `docker compose build backend worker`.
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
  - os valores da tabela de pseudónimos de execuções anteriores também respeitam o `allow:` dos overrides; foi assim que
    a freguesia de R1 (tomada por morada pelo mapa antigo) voltou a ficar real em 25 set 2026;
  - os PDF são gravados com o `/ID` da origem (`no_new_id`): uma nova execução só muda os PDF cujo conteúdo muda.
- Próximo: Fase 4 (montagem fixed/parametric, redação adaptive, editor, formulários), depois de o curador aprovar
  os blocos. Antes: D7 (curador), D8 (esqueletos com os técnicos) e D5 (termos da Gemini API, para a redação adaptativa);
  D6 (Entra ID) continua por decidir com a TI.
