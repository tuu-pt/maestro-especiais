# Maestro Especiais

Agente de IA da TUU para montar, redigir e validar o processo de projeto de instalações elétricas
(MDJ, CTE, MQT/LPU, ficha eletrotécnica, identificação e termo).
Especificação completa: docs/SPEC.md · Mock-up: docs/mockup/maestro-especiais.html
Continuar noutra conta ou máquina (o que não vem com o repositório, .env, arranque): docs/CONTINUAR.md

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
- «Aprovar todas as propostas» (8 out 2026, pedido do utilizador com a D7 provisória): só o papel Curador, no ecrã G
  (Biblioteca), com justificação ≥ 10 caracteres, para o MDJ, o CTE ou os dois (`POST /library/blocks/approve-all`);
  cada bloco fica aprovado em nome de quem carrega, com um evento por bloco e um de resumo; os requisitos do CTE são
  aprovados com o bloco; rejeitados ficam como estão; uma regra de ativação inválida fica por aprovar. O agente não
  carrega no botão.

Decisões da Fase 4 (28 set 2026; as quatro primeiras aprovadas pelo utilizador, o resto [A CONFIRMAR]):
- Guarda de privacidade antes de cada pedido ao LLM: valores `personal_data` da ficha, campos pessoais dos perfis,
  `BlockedTerm` (nomes da equipa; em desenvolvimento semeados das fixtures) e os padrões de app/library/privacy.py.
  Uma ocorrência bloqueia; `LlmCall` guarda o tipo e o sítio, nunca o valor nem o conteúdo.
- D5: `Project.llm_allowed`; desde 8 out 2026 **verdadeiro por omissão** (decisão do utilizador, migração 0018: só os
  projetos novos); só o admin o desliga ou volta a ligar; desligado, HTTP 409 «LLM desligado neste projeto», na auditoria.
- DOCX: rascunho sobre o pacote do MDJ/CTE de R1 (modelo provisório até haver modelo TUU vazio); a exportação oficial
  (Fase 6) só com blocos aprovados e secções revistas (`export_readiness`, já testada).
- Chaves de troços e artigos: `circ.<origem_destino>.<campo>` e `bom.<código>.<campo>`; sem agregados calculados.
- Modelo: Flash-Lite em LLM_MODEL_DRAFTING e LLM_MODEL_EXTRACTION (quota), contra a D10 (Flash) [A CONFIRMAR];
  LLM_MODEL_EMBEDDING vazia (não usada). Ritmo LLM_RPM=10, LLM_RPD=200; geração no worker (fila `llm`) com retoma.
- Alternativa (decisão do utilizador, 28 set 2026): principal Gemini `gemini-3.5-flash-lite`; quando fica indisponível
  (5xx depois das repetições, ex.: 503 «high demand» do nível gratuito), o mesmo pedido, já verificado pela guarda, vai para
  a Groq com `openai/gpt-oss-120b` (LLM_FALLBACK_*, ritmo próprio LLM_FALLBACK_RPM=2).
  GroqProvider sem SDK (httpx, API compatível com OpenAI), espera o `retry-after`. Avaliação R2 (28 set): Flash-Lite 5/5;
  gpt-oss-120b 4/5 (o 5.º com chaves inventadas, que ficam «falta dado»); gemini-3.6-flash rejeitado (NUM-01 com
  números de R2 e 20 pedidos/dia).
- Três fornecedores (decisão do utilizador, 8 out 2026): Gemini, Groq e Claude (Anthropic, SDK `anthropic`, saída
  `json_schema`), todos disponíveis. O principal escolhe-o o admin no ecrã Definições (`AppSetting` «llm.primary»,
  migração 0019, `PUT /settings/llm` com justificação, na auditoria; sem escolha, `LLM_PROVIDER`); os outros seguem
  pela ordem Gemini, Groq, Claude. Muda-se para o seguinte em **qualquer falha do serviço** (5xx, 429 que persiste,
  sem ligação, quota do dia esgotada); a guarda e o JSON inválido não mudam de fornecedor; pausa só quando todos estão
  sem quota. Um fornecedor sem chave ou sem modelo fica de fora. Variáveis próprias `LLM_<FORNECEDOR>_MODEL_*`,
  `_RPM`, `_RPD` e `ANTHROPIC_API_KEY`; vazias, valem as antigas (`LLM_MODEL_*` para o `LLM_PROVIDER`,
  `LLM_FALLBACK_*` para o `LLM_FALLBACK_PROVIDER`). Modelo do Claude por definir (é a 3.ª escolha).
- Texto do agente chega sempre como versão **proposta**; aceitar/rejeitar no diff. Pedidos em linguagem natural idem.
- NUM-01 com lista branca em backend/app/llm/whitelist.yaml; os números copiados das fontes (distâncias
  regulamentares) também são assinalados: ficam para o técnico confirmar (a regra não é relaxada).
- Editor: TipTap 3 (MIT), `diff` (BSD). Fixo editado só depois de desbloquear com justificação; valor da ficha editado
  pede confirmação e fica marcado para a COE-01; um paramétrico editado exporta-se como texto com o estilo do parágrafo.
- Imagem que só existe num projeto de referência não é montada (equipamento desse projeto, Fase 7); a secção diz porquê.
- Perfil do técnico cifrado (Fernet, PROFILE_ENCRYPTION_KEY, `make env-update`); é o de quem confirmou a ficha-base;
  `dev:tecnico` tem um perfil falso evidente com DEV_AUTH. `cryptography` explícito no pyproject.
- Formulários: FE editada célula a célula no XML da folha (app/forms/xlsx.py), não com o openpyxl, para manter as
  listas de validação DGEG e o ActiveX; Identificação e Termo com python-docx pelas etiquetas (docxtpl é LGPL);
  modelos derivados de R1 (`make form-templates`); a secção 4 da Identificação fica para o técnico; «Tipo de
  estabelecimento» = `ele.tipo_utilizacao` (Identificação) e `ele.classificacao` (Termo).
- Relatório de diferenças: `make diff-report` → docs/fase4-diff-R1.md (classes adaptativo / valor / estrutura / defeito).

Decisões da Fase 5 (28 set 2026; as do plano aprovado pelo utilizador, o resto [A CONFIRMAR]):
- Regras determinísticas, sem LLM, uma por ficheiro em backend/app/validation/rules/ (16: REF-01..03, NUM-01, COE-01..06,
  TIP-01, DES-01, CAL-01, CCP-01, CNT-01, TXT-01; EQP-* na Fase 7). CAL-01, NUM-01 e REF-01 da Fase 4 passaram a regras
  (a redação e a ficha importam-nas). Leitura provável determinística (app/validation/likely.py): nunca por maioria.
- Motor (0013): ValidationRun, ValidationIssue (com `fingerprint`: ignorado continua ignorado, o que deixa de aparecer
  fica `fixed`) e PieceFacts (cache por `content_hash`: a revalidação só lê as peças alteradas). Fila RQ `validation`
  (o worker ouve `ingest llm validation`), progresso por SSE; uma edição no editor pede uma revalidação `changed`.
- Peças existentes (0014): MDJ/CTE/Identificação/Termo feitos à mão detetados pelo título; MDJ e CTE viram Document
  `origin = existing`, só leitura, secções da divisão da Fase 3 com os dados pessoais mascarados; a validação lê o
  ficheiro original no backend. Um novo carregamento substitui o anterior.
- Extração de factos (app/validation/extract/): cada extrator só lê as secções do seu tema; números por extenso e uma
  única multiplicação escrita («N pedestais com capacidade de M carregadores em cada» → C8 = 6, e a ambiguidade
  «capacidade» fica na nota); o que não se lê com confiança é «não comparável» (informação).
- [A CONFIRMAR] NUM-01 só no texto do agente; REF-01 no texto humano é aviso com pedido ao curador; REF-02 «por
  confirmar pelo curador» é uma informação por peça (nada é citável enquanto D7 estiver pendente).
- [A CONFIRMAR] COE-01: referência = ficha-base, ou a fonte da ficha (Tabela, depois MQT/LPU) quando não tem valor;
  crítico se diverge a MDJ ou o CTE, aviso se só o MQT/LPU. Luminárias (6 out 2026): por **tipo** (o CTE lista os tipos
  sem quantidades): tipos L#/SNC da lista do CTE/MDJ (secções de iluminação, não de comandos) contra os artigos do
  MQT/LPU (designação «L1», «L8 / L7», «L1 - Luminária…»); referência = MQT, depois LPU; variantes contam como o tipo
  (L5.1, L5.2 → L5); aviso; linha «Tipos de luminárias» na matriz. R1 e R2 coerentes (sem alertas novos).
- [A CONFIRMAR] COE-02 (6 out 2026): as peças desenhadas datam-se pelo mês da carimbadura (`pd.carimbadura.data`, o
  mais recente), não pelo dia do carregamento; são «mais recentes» só num mês posterior ao da confirmação da ficha-base
  (`Piece.date` = `2026-06`, `date_source` = `carimbadura`). Os outros ficheiros continuam pela data de carregamento.
- [A CONFIRMAR] COE-04: forma mais curta = igual (nome curto na capa, obra abreviada na carimbadura); dois ou mais
  campos diferentes ou vazios → «reaproveitada de outro projeto» (C7); técnico comparado entre peças, leitura
  «Confirmar com o perfil do técnico» (C3).
- [A CONFIRMAR] COE-06: referência = Tabela; MDJ+CTE juntas, MQT/LPU à parte (o MQT de R1 também tem H07V-K); rígido
  vs flexível crítico; sem equivalência aprovada, aviso e pedido ao curador; condutores de terra (1G…, secções de
  terras) fora da comparação.
- [A CONFIRMAR] CNT-01 também exige que a MDJ indique a potência a alimentar (C6); COE-03/CNT-01 casam blocos pela chave
  (slug dos títulos): uma peça com títulos diferentes da biblioteca aparece com blocos em falta.
- [A CONFIRMAR] TIP-01: tabela de usos DGEG → palavras da obra (app/validation/rules/tip_01.py); nomes de outros projetos
  do arquivo, exceto a identificação da ficha-base do próprio projeto.
- [A CONFIRMAR] CAL-01: limites de queda de tensão e poder de corte lidos da MDJ; troços da Tabela comparados com o
  limite de «outros usos»; sem limites na MDJ → «não comparável».
- Envio para revisão: `POST /projects/{id}/review-request`, recusado com críticos abertos, sem validação ou com uma
  validação em curso; ignorar exige ≥ 10 caracteres e fica na auditoria.
- Testes: o Playwright passa os ficheiros de R2 como conteúdo (não como caminhos): alguns Chromium
  descartam caminhos com «ç» sem erro.

Decisões da Fase 6 (6 out 2026; as oito do plano aprovadas pelo utilizador, o resto [A CONFIRMAR]):
- Técnico responsável por peça: por omissão quem confirmou a ficha-base; um técnico ou o admin reatribui com
  justificação. Só ele aprova (`POST /documents/{id}/approve`), e só em `in_review` com todas as condições de
  `app/review` (peça montada, ficha-base confirmada e a mesma da peça, secções ativas revistas, blocos aprovados pelo
  curador no estado **atual** do bloco, validação sem críticos). Reabrir (justificação) cria a revisão n+1 (0015).
- Valores manuais na ficha-base (`POST /projects/{id}/ficha/values`, técnico): só Identificação, Imóvel e Alimentação,
  numa revisão em rascunho a reconfirmar; um valor lido de uma fonte corrige-se pelo conflito. Resolve o R1 (obra, CP).
- Revisões: um contador n por peça → ficheiro `V<n>`, cabeçalho `R<nn>`, interface «rev. A, B…».
- Nomes [A CONFIRMAR com a TUU]: `<CÓDIGO>_<PEÇA>_<FASE>_ELE_V<n>` (PE = execução, PL = licenciamento), formulários
  `FichaEletrotecnica`, `IdentificacaoProjeto`, `TermoResponsabilidade`, sem acentos; rascunho `_RASCUNHO-nao-aprovado`.
- Marca de água «RASCUNHO — não aprovado»: forma VML diagonal em todos os cabeçalhos dos .docx; no .xlsm, no cabeçalho
  de impressão da folha (`<headerFooter>`, dentro do XML da folha).
- Peças existentes (auditoria) não se aprovam nem se exportam; só se validam.
- LibreOffice (writer/calc nogui, MPL) na imagem do backend, no `make test-docker` (`SKIP_LIBREOFFICE=1` para saltar) e
  na CI: PDF opcional e verificação de conversão; no Windows sem `soffice`, os testes dele são saltados.
- D9: links assinados pela API (HMAC, `EXPORT_LINK_SECRET`, 24 h) e `X-Service-Token` (`MAESTRO_SERVICE_TOKEN`);
  `make env-update` acrescenta-os a um `.env` existente.
- [A CONFIRMAR] «byte a byte» = conteúdo de cada parte do pacote, mesma ordem e datas no zip (o fluxo comprimido pode
  mudar); a FE só muda o XML da folha, a identificação e o termo só `word/document.xml` (+ cabeçalhos no rascunho).
- Índice (melhoria de 6 out 2026): as entradas são escritas a partir dos títulos da própria peça (app/assembly/toc.py:
  secções omitidas saem, novas e editadas entram, numeração recalculada pelo numbering.xml, marcador `_Toc` do título
  ou um novo `_TocMaestro<n>`); na exportação com LibreOffice, os números de página vêm de um PDF de uma cópia com
  `§n§` antes de cada título (app/export/toc.py) e sai sem `updateFields`: o Word já não pergunta. Sem LibreOffice
  (Windows) ou na descarga rápida do rascunho (`draft.docx`), fica `updateFields`. Fontes métricas compatíveis na
  imagem (Carlito = Calibri, Liberation = Arial/Times, OFL): com elas, as páginas de R1 coincidem com o PDF feito
  pelo Word em 30 de 31 títulos (o índice guardado no .docx de R1 estava desatualizado). [A CONFIRMAR] no Word.
- [A CONFIRMAR] uma entrada editada à mão sai como texto com o estilo do parágrafo de origem; os IDs repetidos de
  imagens e marcadores (fragmentos de R1 e R2) recebem IDs novos, só os repetidos.
- [A CONFIRMAR] descarga: rascunho → redator e técnico; oficial → também o admin; nunca o curador. Pedir o oficial: técnico.
- [A CONFIRMAR] propriedades do .docx: autor, «último a alterar» e empresa = TUU; título `<CÓDIGO> · <peça>`. As
  fixtures de R1/R2 trazem nomes de pessoas em `docProps/core.xml` (a assinalar à equipa; não passam para a exportação).
- O worker também tem `DEV_AUTH` em desenvolvimento (resolve o perfil do técnico nas exportações e na guarda do LLM).

Início de sessão (8 out 2026, pedido do utilizador: «estilo o do Registo de Temas Estratégicos»; até à D6):
- Contas com email e password (`AppUser`, migração 0020) criadas pelo admin com `make create-user EMAIL=… NAME="…"
  ROLES=…` (pede a password, ≥ 10 caracteres; sem página de registo, como no Registo); `make users` lista-as.
- Diferenças em relação ao Registo, de propósito: scrypt da biblioteca padrão (sem dependência nova); cookie
  `maestro_session` HttpOnly, SameSite=Lax, assinado com HMAC (`SESSION_SECRET`), só com o id da conta (nome próprio,
  para não colidir com os cookies das outras apps de apps.tuu.pt); papéis e conta ativa lidos da BD em cada pedido;
  mudar a password termina as outras sessões; 5 passwords erradas bloqueiam 15 min; a mesma resposta para email
  desconhecido, password errada, conta bloqueada ou desativada; nem o email nem a password vão para os logs.
- Com `DEV_AUTH` os utilizadores de desenvolvimento continuam (cabeçalho X-Dev-User); a conta com sessão iniciada
  ganha. Sem `DEV_AUTH`, quem não tem sessão vai para `/entrar`. A D6 (SSO) só substitui `current_user`.
- [A CONFIRMAR] sessão de 12 h (`SESSION_TTL_HOURS`), sem restrição de domínio do email, papéis por conta (não por
  grupos), ids `user:<uuid>` na auditoria e nos perfis dos técnicos.

Decisões da Fase 7 (7 out 2026; as quatro primeiras aprovadas pelo utilizador, o resto [A CONFIRMAR]):
- Fichas técnicas: PDF públicos dos fabricantes em `data/fixtures/fichas-tecnicas/<projeto>/`, sem anonimização, com
  `fichas.json` (origem, data, equipamentos da biblioteca por fabricante + referência ou modelo, o que ficou sem ficha).
  As 17 de R1 foram descarregadas dos sites oficiais em 8 out 2026 (com autorização do utilizador); `make seed-library`
  liga-as aos equipamentos (20 ligações). Os contactos de empresas que o pii-check toma por pessoais ficam no
  `.pii-allowlist.json` da pasta (hashes, só esses valores). Os testes que não precisam delas continuam com os PDFs
  pequenos de backend/tests/pdfs.py.
- Parâmetros lidos por padrões, sem LLM (app/equipment/params.py), no CTE e nas fichas; tudo `extracted` até o curador
  rever; só os revistos decidem a EQP-01.
- Requisitos propostos a partir do texto do CTE; aprovados com o bloco (aprovar um bloco CTE aprova os seus requisitos
  propostos) ou um a um pelo curador.
- A ilustração de um só projeto passa a ser do equipamento da linha de referência acima dela; entra no CTE quando o
  redator ou o técnico confirma ou escolhe esse equipamento no ecrã F (sem escolha, continua omitida).
- [A CONFIRMAR] categorias (lista fechada em app/equipment/__init__.py, pela chave do bloco); um equipamento por linha
  que nomeia um fabricante (lista de marcas em app/equipment/cte.py, ou «da marca X») e um modelo ou uma referência com
  dígitos; as linhas abaixo são características dele, as de antes do primeiro, do bloco inteiro; identidade =
  fabricante + referência + modelo + código + nome (R1 e R2 com a mesma linha dão um só equipamento).
- [A CONFIRMAR] comparação: IP por dígito (um X na ficha para um dígito exigido = «não comparável»), IK por número,
  Euroclasse por ordem; potência e temperatura de cor iguais; os outros mínimos `>=`. Requisitos `>=class`/`>=`/`=`.
  A tensão é só informação, como as dimensões (8 out 2026): nas fichas reais aparecem alimentações, gamas e correntes
  de relés (Hikvision «Max. 30 VDC»), e o «12 V» do CTE de R1 é das fitas LED, não de todas as luminárias. Alcance de
  deteção também em inglês e italiano («Detection distance», «rilevamento», «360° max 14 m»); data de emissão também
  `2020.01.03`. A data no rodapé das fichas da Quitérios é a da geração do PDF e não se lê.
- [A CONFIRMAR] slot = entrada do bloco que nomeia o equipamento, com o do projeto de onde a entrada vem; trocar só
  por um da mesma categoria, com justificação (≥ 10); quantidade do MQT/LPU: luminárias pelo código, o resto pelo
  artigo ligado à chave da ficha (`eq.*`).
- [A CONFIRMAR] EQP-01 crítico só com um parâmetro revisto que falha; aviso para confirmar os lidos; informação para o
  que a ficha não diz. EQP-02: `EQUIPMENT_DATASHEET_MAX_AGE_YEARS` (3), ficha sem data = informação. EQP-03 uma vez por
  equipamento. Categoria «Fichas técnicas», ação `open_equipment` (ecrã F).
- Chave nova `eq.aparelhagem_serie` (estava na SPEC 7.2), sem leitor.

## Comandos
- make setup                 # .venv + dependências Python + npm ci + Chromium do Playwright
- make env                   # gera .env local com segredos aleatórios de desenvolvimento
- docker compose up          # ambiente completo
- make test                  # pytest + vitest
- make test-docker           # pytest num contentor Linux (Windows com Controlo Inteligente de Aplicações); ARGS=...
- make lint                  # ruff + mypy + eslint + tsc
- make e2e                   # Playwright
- make anonymize             # corre tools/anonymize.py (local, fora do Git)
- make pii-check             # procura padrões de dados pessoais em data/fixtures/ (também na CI)
- make seed-library          # propostas da biblioteca e do conhecimento a partir de data/fixtures (idempotente)
- make curator-review        # escreve docs/revisao-curador.md a partir das propostas
- make env-update            # acrescenta ao .env as variáveis novas do .env.example (não mexe nas existentes)
- make form-templates        # modelos vazios dos formulários a partir de R1 (data/fixtures)
- make diff-report           # docs/fase4-diff-R1.md (R1 montado na stack, com os adaptativos gerados)
- make anexo-c-report        # docs/fase5-anexo-c.md (casos do Anexo C na validação; só o Postgres do compose)
- make fichas-report         # docs/fase7-fichas-R1.md (equipamentos de R1 contra as fichas técnicas; só o Postgres do compose)
- make create-user EMAIL=… NAME="…" ROLES=redator,tecnico  # cria ou atualiza uma conta (pede a password)
- make users                 # lista as contas
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
| D4 | Alojamento cloud na UE | ✅ Por agora (8 out 2026, decisão do utilizador): só no PC do utilizador; o alojamento decide-se depois |
| D5 | Termos da Gemini API | ✅ Aceite (8 out 2026, comunicado pelo utilizador): texto de projetos reais pode ir à Google, à Groq e à Anthropic, sempre sem valores nem dados pessoais (marcadores e guarda de privacidade); LLM ligado por omissão, o admin desliga por projeto |
| D6 | Autenticação Entra ID, se aplicável | ✅ Por agora (8 out 2026, decisão do utilizador): contas com email e password, como no Registo de Temas Estratégicos, até haver instruções da TI |
| D7 | Curador | ✅ Provisório (8 out 2026, decisão do utilizador): as propostas da biblioteca dão-se como boas para o piloto e corrigem-se na fase de testes. A aprovação na aplicação continua a ser um ato humano registado (papel Curador); o agente não aprova |
| D8 | Esqueletos da secção 8.3 | ✅ Aceites como estão (8 out 2026, decisão do utilizador); corrigem-se na fase de testes se for preciso |
| D9 | Integração TUU Maestro | Endpoint de exportação no MVP |
| D10 | Gemini Flash | ✅ Alargada (8 out 2026): Gemini, Groq e Claude, principal escolhido pelo admin; Flash-Lite pela quota [A CONFIRMAR]; modelo do Claude por definir pelo utilizador quando for preciso (fica assim) |
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
- Fase: 7 **implementada** (7 out 2026). Fases 0, 1 e 2 concluídas; a 3 está implementada e à espera do curador (D7):
  fecha quando os blocos estiverem aprovados. Até lá, as secções montadas dizem «bloco não aprovado» e só sai o
  rascunho (o conjunto oficial exige os blocos aprovados). As 4, 5 e 6 estão implementadas. Critério da 7 em parte
  (8 out 2026, docs/fase7-fichas-R1.md, `make fichas-report`): dos 32 equipamentos do CTE de R1, 20 têm ficha do
  fabricante; com os parâmetros dados como revistos, 5 cumprem, 1 fica por confirmar (a ficha da tomada schuko não diz
  o IP), 14 não têm requisitos no CTE e **nenhum falha**; 12 ficam sem ficha (descontinuados, só por email, site
  bloqueado ou só documentos parciais, em `fichas.json`). Para fechar: as fichas que faltam (a equipa) e o curador
  rever os parâmetros (D7).
- Feito na Fase 7:
  - biblioteca de equipamentos (0017): 77 equipamentos, 81 parâmetros do CTE e 87 requisitos propostos de R1/R2 por
    `make seed-library`; secção «Equipamentos» em docs/revisao-curador.md;
  - fichas técnicas no S3, leitura por padrões com a página, data e língua; API do curador (rever, corrigir,
    acrescentar, aprovar); slots do CTE montado com alternativas, quantidade e ilustração; EQP-01/02/03;
  - ecrã F (verificação parâmetro a parâmetro, alternativas, escolher com justificação) e separador «Biblioteca de
    equipamentos» no ecrã G.
- Feito a 8 out 2026 (ramo `fase7`): início de sessão com email e password (0020); fichas técnicas de R1 (20/32 equipamentos, nenhum falha; 12 sem ficha
  ignoradas por decisão do utilizador), LLM ligado por omissão (0018), três fornecedores com o principal escolhido no
  ecrã Definições (0019).
- Melhorias de 6 out 2026 (ramo `melhorias`): índice gerado sem `updateFields` (LibreOffice), luminárias na COE-01,
  COE-02 pela data da carimbadura.
- Feito na Fase 6:
  - valores manuais na ficha-base; técnico responsável, aprovação com as condições reais e revisões (0015);
  - DiffView e diff entre revisões; ecrã H (condições com razão e ligação, responsável, data do cabeçalho, aprovar,
    reabrir, histórico, exportações);
  - .docx oficial e rascunho (marca de água) sobre o construtor da Fase 4; formulários só com as partes preenchidas
    alteradas; conjunto .zip com manifesto, PDF opcional, S3 com SHA-256, fila `export` (0016); endpoint D9;
  - verificações de fidelidade automáticas (`app/export/checks.py`) e docs/fase6-verificacao-manual.md (o que se
    confirma à mão no Word e no Excel).
- Feito na Fase 5:
  - motor de validação em worker com revalidação das peças alteradas (0013), peças existentes em modo auditoria (0014),
    extração de factos de todas as peças sem LLM, 16 regras da secção 9;
  - ecrã E: resumo, alertas com filtros, evidência mascarada, leitura provável e ações (abrir no editor/ficha, pedir
    ao curador, ignorar com justificação, reabrir), matriz de coerência 10.E; envio para revisão bloqueado com críticos;
    painel com críticos abertos e novos; ecrã H com as condições reais;
  - docs/fase5-anexo-c.md (`make anexo-c-report`): **14/14 casos** do Anexo C com a leitura provável esperada em R1 e R2
    carregados como auditoria; controlos sem alertas; lista dos outros alertas reais para a equipa rever.
- Feito na Fase 3:
  - dicionário de cabos (designações tal como aparecem e onde, equivalências propostas com evidência) e léxico de
    tipologias (termos incompatíveis com a evidência, C2), migração 0005;
  - MDJ/CTE de R1/R2 partidos em secções com o OOXML original e ida e volta verificada (0006); 95 blocos propostos
    (42 MDJ, 53 CTE) com evidência, marcadores e arquivo (0007, 0008); regras de ativação para o esqueleto 8.3;
    `equipment_slots` no CTE; corpus reduzido do Anexo D, só referências, nada citável (0009);
  - ecrã G: dicionário, léxico, biblioteca (evidência lado a lado, pré-visualização, aprovar/editar/rejeitar, histórico)
    e corpus; decisões só do papel Curador, na auditoria.
- Feito na Fase 4:
  - montagem do MDJ e do CTE a partir da ficha-base confirmada (0010): regras, fixos bloqueados, paramétricos com
    ValueRef, «falta dado», adaptativos por gerar, rascunho .docx sobre o pacote de R1, `export_readiness`;
  - camada de LLM (0011): LlmProvider/GeminiProvider/FakeProvider, LlmClient com D5, guarda, ritmo, repetições,
    Pydantic e LlmCall sem conteúdo; redação adaptativa e pedidos em linguagem natural como propostas, com REF-01 e
    NUM-01; job RQ `llm` com retoma e SSE; avaliação em backend/tests/llm_eval (RUN_LLM_EVAL=1);
  - ecrã D (editor assistido): secções com estado/modo/«não aprovado», TipTap, desbloquear e ativar com justificação,
    confirmação de valores (COE-01), propostas em diff, marcar como revista, formulários pré-preenchidos;
  - formulários (0012): perfil do técnico cifrado, FE, Identificação e Termo; `GET /projects/{id}/forms[/{kind}]`;
  - docs/fase4-diff-R1.md: MDJ 225/268 entradas iguais, CTE 172/242, **zero defeitos**; C1 repetida pelo agente e C2
    não repetida (a deteção é da Fase 5); C3 resolvida pelo perfil.
- Verificado (7 out 2026, Fase 7 e melhorias, Windows 11 + Docker Desktop): `make lint` e `make pii-check` limpos;
  pytest 763 em contentor (`make test-docker`, com o LibreOffice); Vitest 86; Playwright 91 (+ percursos opcionais);
  percurso RUN_EQUIPMENT_JOURNEY verde contra a stack (portinhola de R1 «Cumpre» com a ficha revista, os outros 31
  equipamentos «Sem ficha», a imagem do espelho escolhido no rascunho do CTE); Anexo C 14/14 sem alterações nos casos.
- Verificado (6 out 2026, Fase 6, Windows 11 + Docker Desktop): `make lint` e `make pii-check` limpos; pytest 695 (8
  saltados: os do LibreOffice, que passam no contentor com `make test-docker`: .docx, formulários e conjunto, PDF
  incluído); Vitest 77; Playwright 85 (+ percursos opcionais); percurso RUN_EXPORT_JOURNEY verde contra a stack (R1
  revisto, aprovado e exportado; .zip com os nomes oficiais). O percurso encontrou e corrigiu: o worker sem `DEV_AUTH`
  (o técnico de desenvolvimento sem perfil nas exportações) e uma recusa que não dizia que valores faltavam.
- Verificado (28 set 2026, Fase 5): pytest (suite completa) verde, Vitest 65, Playwright 79 (+ percursos opcionais), `make lint` e
  `make pii-check` limpos; `make anexo-c-report` 14/14; percurso RUN_AUDIT_JOURNEY verde contra a stack (R2 completo com a
  MDJ e o CTE existentes, validação no worker, aviso ignorado, envio bloqueado), capturas em claro, escuro e telemóvel.
  Repetido num PC Windows 11 com Docker Desktop (28 set 2026): pytest 664 em contentor (`make test-docker`), Vitest 66,
  Playwright 79, Anexo C 14/14 sem diferenças, e os percursos de auditoria, R2, curador e R1 no editor (Gemini real)
  verdes. Encontrados e corrigidos: um teste que só passava com caminhos POSIX e textos «chega na Fase 4/5» na interface.
- Verificado na Fase 4 (28 set 2026): pytest 566, Vitest 55, Playwright 74; avaliação com o Gemini real (RUN_LLM_EVAL=1,
  R2): 5/5 sem NUM-01, REF-01 nem dados pessoais; MDJ e CTE de R1 redigidos pelo worker (60 pedidos, 0 bloqueios).
  Percurso RUN_R1_EDITOR_JOURNEY verde, com o Gemini em 503 «high demand» respondido pela alternativa Groq.
  A lista branca da NUM-01 aceita «16 A a 250 V» como «16A-250V» (28 set 2026).
- [A CONFIRMAR] pela equipa:
  - Fase 7: as decisões acima, cada equipamento e requisito de docs/revisao-curador.md (nomes de linhas longas, o
    detetor 360º/180º de R1, os requisitos do bloco aplicados a todos os seus equipamentos) e as fichas técnicas de R1;
  - Fase 6: as decisões acima, em especial a convenção de nomes, os modelos derivados de R1, a verificação manual
    no Word/Excel e os nomes de pessoas em `docProps/core.xml` das fixtures de R1/R2;
  - Fase 5: as decisões acima e os «outros alertas reais» de docs/fase5-anexo-c.md, em especial: R2 com poder de corte
    de 3 kA na Tabela contra o mínimo de 6 kA da MDJ (12 troços); o título da obra nas peças desenhadas de R2
    («Requalificação e modernização…») diferente da LPU; o CTE de R2 com 16 quadros contra 14 da Tabela; R1 com a rua da
    capa diferente da ficha (já conhecido) e o MQT com H07V-K; a leitura de C8 (6 = capacidade dos pedestais?);
  - Fase 4: as decisões acima, em especial os modelos dos formulários e do .docx (derivados de R1), a morada da capa de R1
    diferente da ficha eletrotécnica (docs/fase4-diff-R1.md), Flash-Lite vs D10, e as 95 propostas de blocos por aprovar;
  - Fase 3: as decisões de método acima e cada proposta em docs/revisao-curador.md;
  - mapa de células das 09-Folhas (maps/folha09_tuu.yaml) e a regra de comparação à precisão do menos preciso;
  - potência de cada troço da Tabela = "TOTAL INSTALADO" (em R1/R2 igual a "Norma [kVA]");
  - secção do troço lida da designação do cabo (Circuit.section_mm2);
  - em R2 a LPU lista 16 quadros e a Tabela 14 (Q.SEGURANÇA, Q.DESENF, "Q.UPS" vs "Q.UPS 10kVA"): conflito real a rever;
  - fixtures: códigos postais «NNNN – NNN» (com travessão) que o anonimizador pode não ter apanhado (Identificação de R1,
    FE de R2); `make pii-check` não os deteta. Rever e voltar a anonimizar (a equipa, localmente).
- Biblioteca: `make up`, `make seed-library` (lê só data/fixtures, montada só para leitura no contentor do backend) e
  `make curator-review`. Percurso do curador: `RUN_CURATOR_JOURNEY=1 npm run e2e` (aprova um bloco na BD de
  desenvolvimento; repor com `docker compose down -v` e voltar a semear).
- Percursos com R2: `make up` e depois `RUN_R2_JOURNEY=1 npm run e2e` (criam projetos na BD de desenvolvimento;
  repor com `docker compose down -v`). Percurso da Fase 4: `make up`, `make seed-library` e
  `RUN_R1_EDITOR_JOURNEY=1 npm run e2e` (cria um projeto R1-E2E-… e chama o Gemini duas vezes; um 503 persistente do
  Gemini faz o percurso falhar com a mensagem «o LLM falhou»). Percurso da Fase 5: `make up`, `make seed-library` e
  `RUN_AUDIT_JOURNEY=1 npm run e2e` (cria um projeto E2E-AUD-… com o R2 completo). Percurso da Fase 6: `make up`,
  `make seed-library` e `RUN_EXPORT_JOURNEY=1 npm run e2e` (R1-E2E-EXP-…, sem LLM; aprova **todos** os blocos: repor a BD
  antes de voltar a correr qualquer percurso). Percurso da Fase 7: `make up`, `make seed-library` e
  `RUN_EQUIPMENT_JOURNEY=1 npm run e2e` (R1-E2E-EQP-…; acrescenta uma ficha técnica à portinhola e aprova o bloco da
  entrada de energia: repor a BD depois). O percurso do curador corre em
  último: aprova a INTRODUÇÃO, que o R1 no editor espera «não aprovado» (senão, repor a BD entre os dois). Depois de mudar dependências do
  backend: `docker compose build backend worker`. Depois de atualizar para a Fase 5: `docker compose up -d backend worker`
  (as migrações 0013/0014 correm no arranque do backend e o worker passa a ouvir a fila `validation`).
- Notas de ambiente:
  - `make test` exige o Docker a correr (Postgres do compose);
  - Windows: `make` no PowerShell ou no `cmd`, não no Git Bash; com o Controlo Inteligente de Aplicações o `.venv` não
    carrega a DLL do `psycopg-binary`: pytest com `make test-docker` (ver docs/CONTINUAR.md, secção 8);
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
- Próximo: Fase 8 (piloto: três projetos reais de eletricidade, SPEC 14). Decisões de 8 out 2026 (utilizador): D4 só
  no PC dele, D6 contas com password, D7 e D8 dados como bons e corrigidos nos testes, modelo do Claude mais tarde.
  Falta a equipa rever as Fases 3–7 e um humano com o papel Curador aprovar os blocos na aplicação. Para fechar a 7: as 12 fichas de R1 que faltam (lista em data/fixtures/fichas-tecnicas/R1/fichas.json;
  pô-las na pasta e acrescentar a entrada) e a revisão do curador.
  Antes do uso real da Fase 6: a verificação manual (docs/fase6-verificacao-manual.md), modelos .docx TUU vazios (hoje o
  pacote de R1) e dos formulários, a convenção de nomes confirmada pela TUU, o curador (D7) para haver conjunto oficial.
  Trabalho futuro da Fase 6: PDF assinado,
  integração mais funda com o TUU Maestro (D9). Trabalho futuro da Fase 5: citações com locator
  nas peças humanas, extração assistida por LLM para o que fica «não comparável».
  Sem decisões pendentes que bloqueiem o piloto; D6 e D4 revêem-se quando houver instruções da TI ou da direção.
