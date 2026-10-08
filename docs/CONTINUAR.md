# Continuar o Maestro Especiais noutra conta

Guia para retomar o projeto numa conta nova (do Claude e/ou do GitHub) sem perder contexto.
Escrito a 28 set 2026 (Fase 4), atualizado a 6 out 2026 (Fase 6). A fonte de verdade continua a ser `CLAUDE.md` (regras e
estado) e `docs/SPEC.md` (especificação); este ficheiro diz o que **não** vem com o repositório e
como arrancar.

## 1. O repositório

- `https://github.com/tuu-pt/maestro-especiais` — **privado**, da organização `tuu-pt`, ramo `main`.
- Uma conta pessoal só o vê se for convidada (Settings → Collaborators, ou membro da organização).
  Alternativa: a TUU transfere ou cria um fork privado. **Confirmar com a TUU antes**: o repositório
  tem as fixtures de dois projetos reais da TUU (anonimizadas, mas com emails e o nome de um
  engenheiro da equipa, por decisão de 24 set 2026; ver `CLAUDE.md`, Decisões da Fase 0).
- Para o Claude trabalhar nele: clonar para uma pasta local e abrir o Claude Code nessa pasta.

## 2. O que não vem com o repositório

| O quê | Onde estava | Como repor |
|---|---|---|
| `.env` (segredos e modelos) | raiz do projeto, no `.gitignore` | `make env` e depois preencher à mão (secção 4) |
| `data/private/` (originais, pseudónimos, overrides) | só na máquina da equipa | **não é preciso** para desenvolver; nunca o copiar para a conta pessoal |
| Base de dados e S3 de desenvolvimento | volumes Docker | `make up` + `make seed-library` (a app começa vazia) |
| Conversa, planos e memórias do Claude | `~/.claude/` da conta antiga | não passam; o contexto está neste ficheiro, no `CLAUDE.md` e na SPEC |
| `make` no Windows | winget | `winget install ezwinports.make` (ou correr os comandos Python diretamente) |
| Chaves Gemini e Groq | `.env` | criar chaves na conta/projeto autorizado (secção 4) |

## 3. Arrancar numa máquina nova

Requisitos: Git, Python 3.12, Node 24 (a CI também prova Node 22), Docker Desktop.

```bash
git clone https://github.com/tuu-pt/maestro-especiais.git
cd maestro-especiais
make setup          # .venv, dependências Python, npm ci, Chromium do Playwright
make env            # .env com segredos aleatórios de desenvolvimento
# preencher o .env (secção 4)
make up             # docker compose: Postgres + pgvector, Redis, S3 (SeaweedFS), backend, worker, frontend
make seed-library   # biblioteca e conhecimento a partir de data/fixtures
make test           # pytest + vitest (precisa da stack ligada)
make lint
make e2e
```

Interface em http://localhost:5173 (utilizador de desenvolvimento escolhido no topo).
Contas reais (email e password, sem `DEV_AUTH`): `make create-user EMAIL=nome@tuu.pt NAME="Nome" ROLES=admin`
(pede a password; nunca a escrever no chat) e `make users` para as listar; a página de entrada é `/entrar`.

## 4. O `.env` a preencher

Nunca colar chaves no chat do Claude: escrevem-se só no `.env`.

```
GEMINI_API_KEY=                 # https://aistudio.google.com/apikey (projeto autorizado; a mesma chave serve todos os modelos)
LLM_MODEL_DRAFTING=gemini-3.5-flash-lite
LLM_MODEL_EXTRACTION=gemini-3.5-flash-lite
LLM_MODEL_EMBEDDING=            # vazio: não usado
GROQ_API_KEY=                   # https://console.groq.com/keys (alternativa)
LLM_FALLBACK_PROVIDER=groq
LLM_FALLBACK_MODEL_DRAFTING=openai/gpt-oss-120b
LLM_FALLBACK_MODEL_EXTRACTION=openai/gpt-oss-120b
LLM_FALLBACK_RPM=2
ANTHROPIC_API_KEY=              # https://console.anthropic.com (3.º fornecedor; com LLM_CLAUDE_MODEL_*)
# LLM_<GEMINI|GROQ|CLAUDE>_MODEL_*, _RPM, _RPD: vazias, valem as de cima. O principal escolhe-se no
# ecrã Definições (admin); os outros entram por ordem quando ele falha.
# PROFILE_ENCRYPTION_KEY, EXPORT_LINK_SECRET, MAESTRO_SERVICE_TOKEN, POSTGRES_*, REDIS_*, S3_* são gerados
# pelo make env (num .env existente: make env-update)
```

Num `.env` que já existe, `make env-update` acrescenta as variáveis novas sem mexer nas outras
(desde 8 out 2026: `SESSION_SECRET`, `SESSION_TTL_HOURS`, `SESSION_COOKIE_SECURE`).
Depois de mudar o `.env`: `docker compose up -d backend worker` (o `restart` não relê o `.env`).

## 5. Regras de trabalho (resumo; as completas estão no `CLAUDE.md`)

- Nunca ler, listar nem abrir `data/private/`; nunca correr `make anonymize` nem `tools/anonymize.py`
  (é a equipa que o faz). O `.claude/settings.json` do repositório bloqueia `data/private/`.
- O agente não decide nem calcula; o LLM nunca escreve números, nomes nem valores (`{{v:chave}}`).
- Dados pessoais nunca vão ao LLM nem aos logs. D5: desde 8 out 2026 o LLM está **ligado por omissão**
  (`Project.llm_allowed`, D5 aceite); o admin desliga-o por projeto. Fornecedores: Gemini, Groq e Claude.
- Interface em PT-PT; código, tabelas, endpoints e commits em inglês.
- Uma tarefa, um commit, com testes. **Push só com autorização explícita.**
- Decisões por confirmar seguem a recomendação e ficam registadas como [A CONFIRMAR] no `CLAUDE.md`.
- Nunca escrever nem repetir chaves de API; o utilizador edita o `.env`.

## 6. Onde está o projeto

- Fases 0, 1, 2 concluídas; **3 implementada à espera do curador (D7)**; **4 implementada** (28 set 2026).
- Fase 4, em resumo: montagem do MDJ/CTE a partir da ficha-base, rascunho .docx, camada de LLM
  (D5, guarda de privacidade, ritmo, repetições, alternativa Groq), redação adaptativa como
  propostas em diff, editor (ecrã D), perfil do técnico cifrado, formulários FE/Identificação/Termo,
  `docs/fase4-diff-R1.md` sem defeitos, percurso Playwright de R1 verde.
- Verificado: pytest 566, Vitest 55, Playwright 74, lint e `pii-check` limpos; CI verde até `4e31808`.
- **5 implementada** (28 set 2026): validação com 16 regras, peças existentes (modo auditoria), ecrã E com
  matriz de coerência, envio para revisão bloqueado com críticos; `docs/fase5-anexo-c.md` com 14/14 casos.
  Depois de atualizar: `docker compose up -d backend worker` (migrações 0013/0014 e fila `validation`).
- Verificada num PC Windows 11 com Docker Desktop (28 set 2026, ramo `fase5`): lint, pytest 664 (em contentor,
  `make test-docker`), Vitest 66, Playwright 79, `pii-check`, Anexo C 14/14 sem diferenças e os quatro
  percursos contra a stack (auditoria, R2, curador, R1 no editor com o Gemini real).
- **6 implementada** (6 out 2026, ramo `fase6`): valores manuais na ficha-base, técnico responsável e aprovação com
  as condições reais, revisões (rev. A → B, V0 → V1), DiffView, exportação do .docx oficial e do rascunho com marca
  de água, formulários com os pacotes intactos, conjunto .zip com manifesto e PDF (LibreOffice na imagem), endpoint D9,
  ecrã H. Depois de atualizar: `docker compose build backend worker` (LibreOffice), `make env-update`
  (`EXPORT_LINK_SECRET`, `MAESTRO_SERVICE_TOKEN`) e `docker compose up -d backend worker` (migrações 0015/0016, fila
  `export`). Confirmar à mão no Word e no Excel: `docs/fase6-verificacao-manual.md`.

## 7. O que falta

**Próximo trabalho:** a Fase 7 (equipamentos) está implementada e fecha com as fichas técnicas de R1, que a equipa
coloca em `data/fixtures/fichas-tecnicas/`; a seguir, a Fase 8 (piloto), que depende de D5, D6 e D7. Ver «Próximo»
no `CLAUDE.md`. Rever antes os [A CONFIRMAR] das Fases 5 a 7 e fazer a verificação manual da Fase 6
(`docs/fase6-verificacao-manual.md`).

**Decisões pendentes:** D4 (alojamento: cloud UE ou VPS da TUU), D6 (Entra ID), D7 (curador), D8 (esqueletos com os técnicos), D10 (Flash-Lite; o modelo do Claude
por definir).

**Ações da equipa:** rever os códigos postais «NNNN – NNN» (com travessão) que o anonimizador pode
não ter apanhado nas fixtures (Identificação de R1, FE de R2) e voltar a anonimizar; confirmar a
morada da capa da MDJ de R1 (≠ ficha eletrotécnica, `docs/fase4-diff-R1.md`); rever
`docs/revisao-curador.md`; pedidos da SPEC 15.2 (modelos .docx TUU vazios, mais projetos, etc.).

## 8. Notas que poupam tempo

- **Gemini, nível gratuito:** responde 503 «high demand» em dias de muita procura (confirmado noutro
  projeto Google a 28 set 2026; a página https://aistudio.google.com/status explica que o nível
  gratuito é o primeiro a ser cortado). A alternativa Groq entra sozinha. O `gemini-3.6-flash` foi
  rejeitado (números de R2 copiados e 20 pedidos/dia); os 2.5 dão 404 a utilizadores novos.
- **Groq:** o `gpt-oss-120b` falha com `json_schema` (`json_validate_failed`); o `GroqProvider` passa
  a modo JSON e o Pydantic valida. O nível gratuito limita tokens por minuto: ritmo de 2/min.
- **Avaliação real:** `RUN_LLM_EVAL=1 pytest backend/tests/llm_eval`; outro fornecedor numa corrida:
  `LLM_PROVIDER=groq LLM_MODEL_DRAFTING=openai/gpt-oss-120b` no ambiente.
- **Percursos contra a stack** (criam dados; repor com `docker compose down -v`, `make up`,
  `make seed-library`): `RUN_AUDIT_JOURNEY=1`, `RUN_R2_JOURNEY=1`, `RUN_R1_EDITOR_JOURNEY=1` e, **em
  último**, `RUN_CURATOR_JOURNEY=1` (`npm run e2e` em `frontend/`). O do curador aprova o primeiro bloco
  adaptativo proposto (a INTRODUÇÃO), e o R1 no editor espera-o «não aprovado»: depois do curador, repor a BD.
- **Relatórios gerados:** `make curator-review` → `docs/revisao-curador.md`; `make diff-report` →
  `docs/fase4-diff-R1.md` (com R1 montado e redigido na stack); `make form-templates`.
- **Windows:** o Vite do contentor não recarrega (reiniciar o contentor `frontend`); o Docker
  Desktop com Resource Saver pára ao fim de ~5 min sem contentores; `make test` exige o Docker.
  - Correr o `make` no PowerShell ou no `cmd`, não no Git Bash (as receitas usam `.venv\Scripts\...`).
  - Windows 11 Home precisa do WSL 2 para o Docker Desktop: `wsl --install --no-distribution` (administrador).
  - Com o Controlo Inteligente de Aplicações ligado, o `.venv` não carrega a DLL do `psycopg-binary`
    («Uma política de Controlo de Aplicações bloqueou este ficheiro»): usar `make test-docker` em vez do
    pytest do `make test` (e `make test-docker ARGS="-q backend/tests/test_validation_annex_c.py
    --annex-c-report=docs/fase5-anexo-c.md"` em vez do `make anexo-c-report`). O Vitest corre com `npm --prefix frontend run test`.
  - Mudar a pasta do repositório mantém os volumes (o nome do projeto Compose é fixo): copiar o `.env`
    antigo em vez de `make env`, senão as palavras-passe novas não abrem o Postgres existente.
- Scripts dentro do contentor: `docker compose exec -w /srv/backend -e PYTHONPATH=/srv/backend backend …`
  (senão usa o pacote instalado na imagem, não o código montado).

## 9. Primeira mensagem sugerida na conta nova

> Lê o `CLAUDE.md`, o `docs/CONTINUAR.md` e a SPEC (secções 7.6, 9, 10.F e 14). Confirma que a stack
> arranca (`make up`, `make seed-library`, `make test`). Se já houver fichas técnicas em
> `data/fixtures/fichas-tecnicas/`, propõe o plano para fechar a Fase 7 com elas, uma tarefa por commit, e espera
> pela minha aprovação antes de implementar.
