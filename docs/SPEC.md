# Maestro Especiais: especificação para desenvolvimento

> Agente de IA da TUU – Building Design Management para montar, redigir e validar o processo de projeto de **instalações elétricas**: **MDJ** (memória descritiva e justificativa), **CTE** (condições técnicas gerais e especiais), mapa de quantidades e formulários de licenciamento.
>
> **Versão:** 0.4 · 24 set 2026 · **Estado:** aprovado para desenvolvimento (MVP)
> **Alterações na v0.4:** a aplicação começa vazia e tudo o que aparece nos ecrãs vem dos documentos carregados; não há dados fictícios na interface. A Fase 1 passa a ser "Interface vazia e carregamento de documentos" (os 8 ecrãs, o backend mínimo e os leitores da ficha eletrotécnica e da Tabela de Cálculo); a Fase 2 fica com os restantes leitores (secção 14).
> **Alterações na v0.3:** o MVP passa de ITED para instalações elétricas; fontes de dados, ficha-base, biblioteca de blocos, regras de validação e casos de teste revistos a partir de dois projetos reais da TUU (Anexo C).
> **Referência visual:** `docs/mockup/maestro-especiais.html` (mock-up interativo, ecrãs A–H; os exemplos do mock-up são de ITED/SCIE: servem para o layout, os estados e as interações, não para o conteúdo)

---

## 0. Como usar este documento

Este documento é a fonte de verdade funcional para o desenvolvimento com o Claude Code.

1. Coloque este ficheiro em `docs/SPEC.md` e o mock-up em `docs/mockup/maestro-especiais.html`.
2. Copie o **Anexo A** para `CLAUDE.md` na raiz do repositório. O Claude Code lê esse ficheiro automaticamente em cada sessão.
3. Trabalhe **uma fase de cada vez** (secção 14). Comece cada fase em *plan mode*, reveja o plano e só depois deixe implementar.
4. As secções marcadas com **[A CONFIRMAR]** são decisões que a equipa ainda tem de tomar (secção 16). Até lá, o Claude Code segue a recomendação indicada.
5. Os projetos reais de referência ficam **anonimizados** em `data/fixtures/` e os originais em `data/private/` (fora do Git). Ver secção 12.2.

Convenção de língua: **interface em PT-PT, código em inglês** (nomes de variáveis, tabelas, endpoints, commits).

---

## 1. Contexto e objetivo

O departamento de instalações especiais da TUU produz, para cada projeto de eletricidade, um conjunto de peças que têm de ser coerentes entre si:

| Peça | Formato atual | Observações |
|---|---|---|
| Memória descritiva e justificativa (MDJ) | `.docx` com modelo TUU | Cerca de 3 000 palavras; cerca de 75% do texto repete-se entre projetos |
| Condições técnicas (CTE) | `.docx` com modelo TUU | Condições técnicas gerais + especiais, com equipamentos de referência "ou equivalente" e imagens ilustrativas |
| Mapa de quantidades (MQT) ou lista de preços unitários (LPU) | `.xlsx` | Capítulos e artigos codificados |
| Ficha eletrotécnica | `.xlsm` (modelo DGEG, versão `FE_v.20190222`) | Células fixas |
| Identificação do projeto | `.docx` (art. 20.º do DL 96/2017) | Formulário |
| Termo de responsabilidade | `.docx` (art. 5.º do DL 96/2017) | Formulário, assinado pelo técnico |
| Folhas de cálculo | `.xls` "09-Folha de Cálculo" (uma por troço) e `.xlsx` "Tabela de Cálculo" (resumo) | Modelos TUU com estrutura fixa |
| Peças desenhadas | `.dwg` + `.pdf` (+ `.dwfx`) | Índice EL001…, plantas, esquemas de quadros |

**Objetivo:** reduzir o tempo de produção deste conjunto e eliminar as incoerências entre peças, sem retirar ao projetista a decisão e a responsabilidade.

**Meta do piloto** (a medir, não garantida): reduzir em pelo menos 40% o tempo de produção de MDJ + CTE + formulários de um projeto de eletricidade, com zero incoerências de identificação, potência e cabos nas peças aprovadas.

---

## 2. Âmbito

### 2.1 MVP (piloto)

- **Especialidade: instalações elétricas de serviço particular (BT).**
- Documentos gerados: MDJ e CTE.
- Formulários pré-preenchidos a partir da ficha-base: Ficha eletrotécnica, Identificação do projeto e Termo de responsabilidade (sem assinatura nem data).
- Documentos verificados (não gerados): MQT/LPU, Tabela de Cálculo e PDF das peças desenhadas.
- Todos os ecrãs do mock-up (A–H), com conteúdos de eletricidade.
- Exportação `.docx` com os modelos TUU e `.xlsm` da ficha eletrotécnica.

### 2.2 Fora do âmbito do MVP

- ITED, SCIE, AVAC e restantes especialidades. O modelo de dados já tem de as suportar (campo `specialty`).
- Leitura de DWG, IFC e Revit, e contagem de símbolos em plantas.
- Importação de exportações de software de cálculo (ex.: CSV do software Hager).
- Qualquer cálculo ou dimensionamento feito pelo agente.
- Assinatura digital e submissão a entidades (DGEG, E-REDES, câmaras).
- Integração profunda com o TUU Maestro (no MVP basta um endpoint de exportação).

---

## 3. Princípios não negociáveis

Estes princípios têm de estar refletidos no código, nos testes e na interface. Nenhuma funcionalidade os pode contornar.

| # | Princípio | Implicação técnica |
|---|---|---|
| P1 | **O agente não decide.** Propõe e sinaliza; uma pessoa confirma. | Conflitos, correções e aprovações exigem uma ação humana registada. Nada é aplicado automaticamente a um documento. |
| P2 | **O agente não calcula.** | Os valores vêm da ficha-base e das folhas de cálculo. O LLM **não escreve números**: escreve *placeholders* que o backend resolve (8.4). As verificações da regra CAL-01 comparam valores já existentes na folha, sem os recalcular. |
| P3 | **Tudo é rastreável.** | Cada bloco e parágrafo guarda a origem (bloco da biblioteca, projeto de arquivo, regulamento, célula de cálculo, ficha-base). |
| P4 | **Só se cita o que existe e está em vigor.** | Uma citação só é válida se apontar para um documento do corpus marcado como `citable`. |
| P5 | **A ficha-base é a fonte de verdade**, mas pode estar errada. | As peças comparam-se com a ficha. Quando uma fonte é mais recente do que a ficha, propõe-se atualizar a ficha, não as peças. |
| P6 | **O texto gerado fica visível até ser revisto.** | Estado por secção: `todo` → `generated` → `reviewed`. Só se aprova com todas as secções `reviewed` e sem alertas críticos. |
| P7 | **Auditoria completa.** | Todas as ações (agente e pessoas) ficam num registo imutável. |
| P8 | **O agente nunca assina nem data.** | Os formulários saem com os campos de identificação pré-preenchidos, mas a data, a assinatura e a declaração ficam sempre para o técnico. |
| P9 | **Dados pessoais nunca vão para o LLM.** | Nomes, NIF, CC, contactos, números DGEG/OET e coordenadas entram só por *placeholder* e são resolvidos no backend na exportação. |

---

## 4. Utilizadores e papéis

| Papel | Pode |
|---|---|
| **Redator** | Criar projetos e fichas-base, gerar e editar documentos, correr validações, marcar secções como revistas. |
| **Técnico responsável** | Tudo o que o redator pode, mais resolver conflitos da ficha-base, confirmar revisões e aprovar documentos. Os seus dados profissionais (n.º DGEG, OET/OE, CC, NIF, contactos) ficam no **perfil**, cifrados, e só são inseridos nos formulários na exportação. |
| **Curador** | Gerir o corpus regulamentar, a biblioteca de blocos, o arquivo de referência, o dicionário de cabos e a biblioteca de equipamentos. |
| **Administrador** | Gerir utilizadores, modelos `.docx`/`.xlsm`, regras de validação e integrações. |

Uma pessoa pode ter vários papéis. A aprovação de um documento tem de ser feita por um técnico responsável atribuído a esse documento.

---

## 5. Arquitetura

```
┌──────────────────────────────┐
│  Frontend (React + TS)       │  ecrãs A–H, editor de secções, diffs
└──────────────┬───────────────┘
               │ REST/JSON (+ SSE para progresso)
┌──────────────▼───────────────┐      ┌──────────────────────┐
│  API (FastAPI)               │─────▶│  PostgreSQL + pgvector│
│  auth, projetos, ficha-base, │      │  dados, blocos,       │
│  documentos, validação       │      │  corpus, auditoria    │
└──────┬───────────────┬───────┘      └──────────────────────┘
       │ fila (Redis)  │              ┌──────────────────────┐
┌──────▼───────────────▼───────┐─────▶│  Armazenamento S3     │
│  Workers                     │      │  xls/xlsx/xlsm,       │
│  ingestão · montagem ·       │      │  PDF, docx            │
│  redação · validação ·       │      └──────────────────────┘
│  exportação                  │      ┌──────────────────────┐
└──────────────┬───────────────┘─────▶│  API Gemini (LLM +    │
               │                      │  embeddings) via      │
               │                      │  camada llm/ própria  │
               └──────────────────────┴──────────────────────┘
```

- As operações longas (ingestão, montagem, redação, validação, exportação) correm em *workers* e reportam progresso ao frontend por SSE.
- O LLM é chamado **apenas pelos workers**, através de um único módulo (`llm/`), com registo de fornecedor, prompt, modelo, tokens e custo por chamada.
- A camada `llm/` é **independente do fornecedor** (6.1). Trocar de modelo ou de fornecedor é uma alteração de configuração, não de código.
- A maior parte do documento é montada **sem LLM** (blocos fixos e paramétricos, secção 8.3). O LLM só adapta blocos que precisam de texto específico do projeto.

---

## 6. Stack recomendada **[A CONFIRMAR]**

| Camada | Recomendação | Porquê | Alternativa |
|---|---|---|---|
| Frontend | React 18 + TypeScript + Vite · React Router · TanStack Query | Padrão maduro e bem suportado pelo Claude Code | — |
| Editor de secções | TipTap (ProseMirror) com marcas próprias: `citation`, `value`, `generated`, `locked` | Etiquetas de origem, realce de texto gerado e blocos fixos protegidos | Lexical |
| Estilos | CSS variables (tokens do mock-up, secção 13) + CSS Modules | Reproduz o mock-up com fidelidade | Tailwind com os mesmos tokens |
| Backend | Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2 · Alembic | A equipa já usa Python e há bibliotecas para docx, xls/xlsx e PDF | Java Spring Boot |
| Jobs | RQ + Redis | Simples e suficiente para o piloto | Celery |
| Base de dados | PostgreSQL 16 + pgvector · pesquisa de texto com configuração `portuguese` | Dados relacionais e pesquisa híbrida no mesmo sítio | MySQL + base vetorial separada |
| Ficheiros | S3 compatível (SeaweedFS em desenvolvimento) | Versões de ficheiros e URLs assinados | Disco local no piloto |
| XLSX / XLSM | `openpyxl` (com `keep_vba=True` para a ficha eletrotécnica) | Leitura por célula e escrita preservando macros | — |
| XLS (formato antigo) | `xlrd` | As "09-Folha de Cálculo" são `.xls` | Conversão prévia com LibreOffice |
| PDF | `pypdfium2` (BSD/Apache; decidido em 24 set 2026: o `pdfplumber` levava ~12 s por página no PDF de R2) | Índice e carimbadura das peças desenhadas; mais tarde legendas e fichas técnicas | `pdfplumber` (lento); PyMuPDF só em `tools/` (AGPL) |
| DOCX | `python-docx` + `docxcompose` para montar blocos preservando OOXML · `docxtpl` para os formulários | Os modelos TUU continuam a ser editados em Word | — |
| LLM | **Gemini Flash** via Gemini API (SDK `google-genai`) · modelo por variável de ambiente · saídas em JSON Schema | Quota gratuita; bom equilíbrio entre qualidade e limites | Flash-Lite para extração · outro fornecedor pela mesma interface |
| Embeddings | Modelo de embeddings do Gemini (mesma chave) | Multilingue e incluído na quota gratuita | Modelo multilingue alojado internamente |
| Autenticação | OIDC · Microsoft Entra ID, se a TUU usar Microsoft 365 **[A CONFIRMAR]** | SSO da empresa | Keycloak |
| Testes | pytest · Vitest · Playwright (E2E) | A equipa já usa Playwright | — |
| Deploy | Docker Compose · alojamento na UE **[A CONFIRMAR]** | Dados de clientes ficam na UE | Servidor interno |
| Fase posterior | `ezdxf` + conversor DWG→DXF · `ifcopenshell` | Contagens a partir de blocos DWG ou IFC | — |

### 6.1 Camada de LLM independente do fornecedor

Toda a aplicação fala com o LLM através de uma interface própria em `backend/app/llm/`. Nenhum outro módulo importa SDKs de fornecedores.

```python
class LlmProvider(Protocol):          # o fornecedor: só transporte, sem regras
    name: str
    def generate(self, *, model: str, system: str, messages: list[Message],
                 json_schema: dict[str, Any], temperature: float) -> RawResponse: ...
    def embed(self, texts: list[str], *, model: str,
              task: Literal["document", "query"]) -> list[list[float]]: ...

class LlmClient:                      # o que a aplicação usa (Fase 4)
    def generate(self, db, *, project, purpose, prompt_version, system, messages,
                 schema: type[T], section_id=None, profile=None) -> tuple[T, LlmCall]: ...
```

`LlmClient.generate` faz, por esta ordem: verificação da D5 (`Project.llm_allowed`, verdadeiro por omissão desde
8 out 2026; desligado pelo admin, HTTP 409 «LLM desligado neste projeto», na auditoria) → guarda de privacidade → ritmo (por minuto e por dia) → repetições
em 429/5xx com espera exponencial → validação Pydantic (uma repetição com o erro) → registo
`LlmCall` **sem conteúdo** (fornecedor, modelo, finalidade, versão do prompt, tokens, ms, estado e,
se bloqueado, o tipo e o sítio da ocorrência, nunca o valor).
A guarda junta os valores `personal_data` da ficha do projeto, os campos pessoais dos perfis dos
técnicos, a lista `BlockedTerm` (nomes da equipa; em desenvolvimento semeada das fixtures) e os
padrões de `app/library/privacy.py`. Qualquer ocorrência bloqueia o envio.

- Implementação inicial: `GeminiProvider`. Deve ser possível acrescentar outro fornecedor sem alterar o resto do código.
- Configuração por finalidade (variáveis de ambiente):

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=                       # chave de um projeto Google da TUU, nunca pessoal
LLM_MODEL_DRAFTING=<versão estável mais recente do Gemini Flash>   # na Fase 4: Flash-Lite [A CONFIRMAR, D10]
LLM_MODEL_EXTRACTION=<Gemini Flash; Flash-Lite se a quota apertar>
LLM_RPM=10                            # pedidos por minuto (quota gratuita)
LLM_RPD=200                           # pedidos por dia; esgotado → geração em pausa, retoma depois
LLM_MODEL_EMBEDDING=<modelo de embeddings do Gemini>
EMBEDDING_DIM=768                     # tem de coincidir com a coluna pgvector
```

- **Nomes de modelos nunca no código**: só na configuração. Confirmar os nomes atuais no Google AI Studio.
- **Limites da quota gratuita**: controlo do ritmo de pedidos (por minuto e por dia, configurável), repetição com espera exponencial em 429/503 e indicação ao utilizador quando um pedido está em fila. A geração retoma a partir do último bloco concluído.
- **Validação da saída**: resposta JSON sempre validada com Pydantic. Se falhar, repete uma vez com o erro no pedido; se voltar a falhar, o bloco fica em `todo` com a mensagem de erro.
- **Fornecedores** (8 out 2026): Gemini, Groq e Claude (Anthropic). O admin escolhe o principal no
  ecrã Definições (`PUT /settings/llm`, com justificação, na auditoria); os outros seguem pela ordem
  Gemini, Groq, Claude. Em qualquer falha do serviço (5xx, 429 que persiste depois das repetições,
  sem ligação, quota do dia esgotada) o mesmo pedido, já verificado pela guarda, segue para o
  seguinte, com ritmo próprio; a guarda e o JSON inválido não mudam de fornecedor. Um fornecedor sem
  chave ou sem modelo fica de fora. Variáveis `ANTHROPIC_API_KEY`, `LLM_<GEMINI|GROQ|CLAUDE>_MODEL_*`,
  `_RPM` e `_RPD`; vazias, valem `LLM_MODEL_*` (para `LLM_PROVIDER`) e `LLM_FALLBACK_*` (para
  `LLM_FALLBACK_PROVIDER`). O `LlmCall` regista o fornecedor e o modelo que responderam.
- **Fila**: a geração corre no worker (fila RQ `llm`), com o progresso por SSE no canal do projeto
  (`queued`, `generating`, `generated`, `failed`, `paused`).
- **Avaliação**: `backend/tests/llm_eval/` (`RUN_LLM_EVAL=1`) com casos fixos (a partir das *fixtures* anonimizadas) e verificações automáticas (zero NUM-01, zero TIP-01, blocos obrigatórios presentes) para comparar modelos e prompts antes de os trocar.
- **Mudar a dimensão dos embeddings** obriga a reindexar (`make reindex`).

---

## 7. Modelo de dados

Nomes em inglês. Todas as tabelas têm `id` (UUID), `created_at`, `updated_at` e `created_by`, salvo indicação em contrário.

### 7.1 Projeto e ficha-base

- **Project**: `code` (ex.: `MBERAL`), `name`, `building_type` (moradia unifamiliar, biblioteca…), `phase` (licenciamento | execução), `specialties[]`, `public_procurement` (bool, ativa CCP-01), `status`.
- **ProjectFile**: `project_id`, `kind` (ficha_eletrotecnica | calc_summary | calc_circuit | mqt | lpu | drawing_pdf | drawing_dwg | archive_docx | other), `filename`, `storage_key`, `version_label` (ex.: `V0`, `V1.1`), `file_date`, `checksum`, `template_version` (ex.: `FE_v.20190222`).
- **FichaRevision**: `project_id`, `label` (rev. A, B…), `status` (draft | confirmed | superseded), `confirmed_by`, `confirmed_at`.
- **FichaValue**: `revision_id`, `key` (chave estável, ver 7.2), `group`, `label_pt`, `value` (JSON), `unit`, `personal_data` (bool), `status` (confirmed | conflict | pending), `source_type` (ficha_eletrotecnica | calc | mqt | drawing | manual), `source_ref` (ex.: `Ficha Eletrotecnica!P29`, `Tabela!linha 9`, `EL001 índice`), `source_file_id`.
- **FichaConflict**: `value_id` **ou** `circuit_id` + `field` (um conflito é de um valor da ficha ou de um campo de um troço, CHECK na BD), `candidates` (JSON: valor, fonte, data), `resolved_value`, `resolved_by`, `resolved_at`, `note`. A mesma fonte pode divergir de si própria (páginas do PDF): um candidato por valor.
- **ProjectFile.ingest_warnings** (JSON): avisos da última leitura, à parte do resumo (`ingest_message`), sem valores.
- **Circuit** (linha da Tabela de Cálculo; pertence a uma `FichaRevision`): `origin`, `destination`, `kva`, `voltage_v`, `protection_type` (D | F), `ib_a`, `in_a`, `idn_ma`, `iz_a`, `i2_a`, `iz145_a`, `cable_raw`, `cable_normalized`, `length_m`, `vd_section_pct`, `vd_upstream_pct`, `vd_total_pct`, `breaking_capacity_ka`, `pole_type` (MON | MUL), `installation` (TUB | EST | ENT | AR), `phases` (1 | 3), `insulation`, `conductor` (Cu | Al), `ref_method`, `rtiebt_table`, `section_mm2` (lida da designação do cabo, [A CONFIRMAR]), `source_ref`.
- **CircuitSheet** (uma 09-Folha; pertence a uma `FichaRevision`): `source_file_id`, `origin_hint` e `destination_hint` (do nome do ficheiro: a folha não diz qual é o troço), `template`, `values` (JSON: campo → valor e célula), `circuit_ids` (um troço ou vários iguais, ex.: CVE 1…5), `link_status` (rule | manual | unlinked), `linked_by`, `linked_at`.
- **BomItem** (uma linha do MQT/LPU; pertence a uma `FichaRevision`): `source_file_id`, `variant` (mqt | lpu), `row_index`, `source_ref`, `code`, `level`, `parent_code`, `kind` (chapter | subchapter | article | description | note | total), `designation`, `unit`, `quantity`, `unit_price`, `total`, `chapter_total`, `link_key` (chave da 7.2), `link_status` (rule | manual | unlinked), `link_rule`, `linked_by`, `linked_at`. Uma revisão nova copia `Circuit`, `CircuitSheet` e `BomItem`.

### 7.2 Chaves da ficha-base (eletricidade)

| Grupo | Chaves (exemplos) | Origem principal |
|---|---|---|
| Identificação | `id.requerente.nome`\*, `id.requerente.nif`\*, `id.requerente.morada`\*, `id.requerente.email`\*, `id.requerente.cp`\*, `id.obra.designacao`, `id.local.rua`\*, `id.local.cp`, `id.local.freguesia`, `id.local.concelho`, `id.local.distrito`, `id.local.gps`\*, `id.local.nip` | Ficha eletrotécnica: nome C5, NIF Q5, email J6, morada C7, código postal do requerente C8, freguesia C15, concelho M15, distrito Q15, rua G16, GPS Q16, NIP E29 (confirmado com R1/R2). A designação da obra e o código postal do local não estão na ficha: MQT/LPU ou manual |
| Imóvel | `ele.descricao_imovel` (Unifamiliar, Outros…), `ele.classificacao` (Locais de habitação, Estabelecimentos recebendo público…), `ele.tipo_utilizacao` (Habitação, Escritório…), `ele.instalacao` (Nova, Existente), `building.pisos[]` | Ficha eletrotécnica (F23, F24, M29, Q23) · manual |
| Alimentação | `ele.tipo_instalacao` (A, B, C), `ele.entrada` (Mono, Trif), `ele.potencia_instalada_kva`, `ele.fator_simultaneidade`, `ele.potencia_alimentar_kva`, `ele.potencia_existente_kva`, `ele.n_ramais`, `ele.tensao_resp_kv`, `ele.contagem` (nova, existente, localização) | Ficha eletrotécnica (B29, O29, P29, Q29, R29, Q24; I44 é a potência total do tipo C, não a contagem) · Tabela de Cálculo (1.ª linha) · manual |
| Distribuição | `ele.quadros[]` (nomes, derivados dos `Circuit`), `ele.pdc_minimo_ka`, `ele.cabos[]` (designações normalizadas), `ele.esquemas_terra[]` (TT, IT, TN), `ele.resistencia_terra_max_ohm` | Tabela de Cálculo · manual |
| Sistemas | `sys.iluminacao_seguranca`, `sys.knx`, `sys.sadi` (loops, zonas), `sys.fv` (potência kW, n.º módulos, Wp, strings, inversor), `sys.ve` (n.º carregadores, kW, obrigatórios), `sys.ups[]`, `sys.audiovisual`, `sys.videoporteiro`, `sys.rpc_classe_minima` | Tabela de Cálculo (destinos CVE, UPS, Q.FV…) · manual |
| Equipamentos | `eq.luminarias[]` (código L1…, descrição, modelo), `eq.portinhola`, `eq.quadros_modelo[]`, `eq.aparelhagem_serie` | Legenda do PDF · biblioteca · manual |
| Peças desenhadas | `pd.indice[]` (código EL001…, título, data, revisão), `pd.n_paginas_pdf`, `pd.folhas[]` (código e título da carimbadura de cada página), `pd.carimbadura.especialidade`, `.fase`, `.data`, `.codigo` | PDF (folha de índice e carimbadura de cada página); a carimbadura dá também `id.requerente.nome` e `id.obra.designacao`, e a LPU o adjudicante e a designação |

\* `personal_data = true`.

### 7.3 Biblioteca de blocos e documentos

- **TemplateBlock**: `key` (ex.: `ele.mdj.dimensionamento_eletrico.quedas_de_tensao`: slug do título de nível 1 e, se houver, do nível 2), `doc_type` (MDJ | CTE), `specialty`, `kind` (cover | index | block | signature), `level` (1 = faixa de título numa tabela de **1 linha e 2 células** com texto; 2 = estilo «heading 2», `Ttulo2` no Word em português), `title`, `order`, `mode` (fixed | parametric | adaptive), `activation_rule` (texto na linguagem de 8.3) e `activation_ast` (a árvore JSON que se avalia), `body_template` (lista de parágrafos `{mode, project, units, text, ooxml, keys, single_source, note}`: `text` e `ooxml` com `{{v:…}}` nos fixos e paramétricos, vazios nos adaptativos), `locked_ooxml` (o bloco inteiro, quando nenhum parágrafo é adaptativo), `ooxml_rels` (por projeto: as relações usadas; imagens no S3 por SHA-256), `required_keys[]`, `equipment_slots[]` (CTE: `{entry, reasons, projects}`), `archive_refs[]` (`arc:<projeto>:<key>`), `projects[]` (onde foi encontrado), `source_refs[]` (secções de origem), `notes[]` (para o curador), `version`, `status` (proposed | approved | rejected) e `reviewed_by` (o `approved_by` quando aprovado). Um bloco nunca guarda dados do projeto nem pessoais.
- **SourceDocument**, **SourceSection** (Fase 3): cada MDJ/CTE de referência partido em secções (capa, índice, blocos, assinatura), cada secção com os seus elementos do corpo em OOXML tal como estão (`ooxml`), as relações que usa (`rels`) e a evidência para o curador (`units`: texto com marcadores e dados pessoais mascarados). O pacote do documento (o .docx com o corpo vazio: estilos, numeração, tema, cabeçalhos) fica no S3 por SHA-256; pacote + fragmentos reconstituem o documento (teste de ida e volta). O cabeçalho tem o técnico, a data e a revisão: fica no pacote; no rascunho da Fase 4, o nome do técnico e o mês/ano passam a marcadores (`tec.nome`, `doc.data`).
- **Document**: `project_id`, `type` (MDJ | CTE | FICHA_ELE | IDENTIFICACAO | TERMO), `specialty`, `template_id`, `ficha_revision_id`, `status` (draft | in_review | approved), `responsible_user_id` (Fase 6: o **técnico responsável atribuído**, por omissão quem confirmou a ficha-base; um técnico ou o admin reatribui com justificação), `origin` (assembled | existing), `revision` (n: ficheiro `V<n>`, cabeçalho `R<nn>`, interface «rev. A, B…»), `approved_by/at`, `header_date` (mês/ano do cabeçalho, só se o técnico o escrever, P8).
- **DocumentRevision** (Fase 6): cada aprovação de uma peça: `number`, `approved_by/at`, `ficha_revision_id`, `header_date`, instantâneo das secções (`section_id`, `order`, `title`, versão atual, ativa) e, quando reaberta, `reopened_by/at` e `reopen_reason`. Estados da peça: `draft` → `in_review` (pedido de revisão da Fase 5, bloqueado com críticos) → `approved` (só o técnico atribuído, com todas as condições) → reaberta como revisão n+1 (`draft`). Numa peça aprovada, nenhuma secção muda (HTTP 409 «reabra»).
- **Export** (Fase 6): rascunho ou conjunto oficial, `status` (queued | running | done | failed), ficheiros (`name`, `piece`, `revision`, `sha256`, `size`, chave S3 sem o nome do ficheiro), `manifest`, .zip (nome, chave, SHA-256).
- **Section** (Fase 4): `document_id`, `block_id`, `block_key`, `block_version` e `block_status` (o estado do bloco quando foi montado: «bloco não aprovado» enquanto o curador não aprovar), `order`, `title`, `level`, `kind`, `mode`, `active` e `active_reason` (resultado da regra de ativação e a razão em português), `activation_override` (quem ativou ou desativou, com justificação), `status` (todo | generated | reviewed | alert) e `status_note`, `missing_keys[]`, `locked` e `unlocked` (bloco fixo desbloqueado com justificação), `equipment_slots[]` (vazios, marcados «Fase 7»), `current_version`, `reviewed_by/at`.
- **SectionVersion**: `section_id`, `number`, `content` (JSON TipTap), `status` (current | proposed | rejected | superseded: o texto do agente chega como **proposta** e só passa a atual quando uma pessoa a aceita no diff), `author_type` (system | agent | human), `llm_call_id`, `request` (pedido em linguagem natural), `missing_data[]`, `assumptions[]`, `issues[]` (NUM-01, REF-01), `created_by`.
- **Conteúdo TipTap**: nós `locked` (fixos, com a entrada do bloco; o OOXML vem do bloco), `pending` (adaptativo por gerar) e `paragraph`; marcas `value` (`key`, `anchor`; os valores pessoais aparecem mascarados), `generated` (texto do agente) e `citation`. Um valor da ficha editado à mão pede confirmação e fica marcado para a COE-01 (Fase 5).
- **Citation**: `section_version_id`, `anchor` (id do nó no conteúdo), `kind` (regulation | archive | block | calc | ficha | datasheet), `target_id`, `locator` (capítulo, página, célula).
- **ValueRef**: `section_version_id`, `anchor`, `key`, `ficha_value_id` ou `circuit_id`/`bom_item_id` + campo, `personal`, `rendered_text` (texto resolvido no momento; vazio nos pessoais), `edited` (valor alterado à mão, para a COE-01).
- **TechnicianProfile** (Fase 4): `user_id` e os dados do técnico (`tec.*`, `doc.local`) num JSON cifrado com Fernet (`PROFILE_ENCRYPTION_KEY`). Só o backend o lê: assinatura, rascunho e formulários. Os campos pessoais vão para a guarda de privacidade; nunca vão ao LLM. Em desenvolvimento, `dev:tecnico` tem um perfil falso evidente.
- **LlmCall** e **BlockedTerm** (Fase 4): o registo de cada pedido ao LLM, sem conteúdo, e os nomes que a guarda bloqueia.

### 7.4 Validação

- **ValidationRun**: `project_id`, `ficha_revision_id`, `document_ids[]`, `pieces[]` (as peças lidas: referência, tipo, origem, data), `trigger` (full | changed: revalidação depois de uma edição), `status` (queued | running | done | failed), `message`, `started_at`, `finished_at`, `totals`, `matrix` (a matriz de coerência de 10.E, mascarada). Corre no worker (fila `validation`), com progresso por SSE.
- **ValidationIssue**: `run_id`, `order`, `rule_id` (secção 9), `severity` (critical | warning | info), `category`, `fingerprint` (a mesma constatação em duas execuções: um alerta ignorado continua ignorado; um alerta que deixa de aparecer passa a `fixed`), `location` (peça, secção, âncora, célula ou página), `message_pt`, `evidence` (JSON, sempre mascarada), `likely_reading` (ex.: "erro provável na MDJ"), `suggested_fix` (opcional), `actions[]` (abrir no editor, abrir na ficha, pedir ao curador, confirmar na folha, ignorar), `new` (não estava na execução anterior: o painel mostra-o), `status` (open | fixed | ignored), `ignored_reason` (obrigatória, na auditoria), `resolved_by`, `resolved_at`.
- **PieceFacts** (Fase 5): o que os extratores leram de cada peça (`facts`, `paragraphs`, `sections`), pelo `content_hash` da peça: uma revalidação só volta a ler as peças que mudaram. Pode conter valores pessoais (fica no backend, como a ficha-base); nunca sai sem máscara.
- **Peças**: tudo o que se compara com a ficha-base. MDJ e CTE montados (`Document.origin = assembled`) ou feitos à mão e carregados para auditoria (`origin = existing`, só leitura, `source_file_id`; tipos de ficheiro `mdj_docx`, `cte_docx`, detetados pelo título); identificação e termo (`identificacao_docx`, `termo_docx`, lidos pelas etiquetas); ficha eletrotécnica, Tabela de Cálculo, MQT/LPU e desenhos, relidos com os leitores das Fases 1 e 2 (só o ficheiro mais recente de cada tipo).

### 7.5 Conhecimento

- **RegulationDoc**: `code`, `title`, `kind` (diploma | guia | especificacao | norma), `edition`, `issuer`, `scope` (âmbito), `specialties[]`, `status` (in_force | revoked | reference_only; vazio até o curador decidir), `citable` (bool; só verdadeiro com o documento confirmado e em vigor), `copyrighted`, `license_note` (normas com direitos de autor: só título e âmbito), `last_checked_at`, `review_status` (proposed | confirmed | rejected), `reviewed_by` (o curador), `found_in[]` e `found_count` (onde os projetos de referência o citam). Nunca guarda o texto integral.
- **RegulationChunk**: `doc_id`, `locator`, `text`, `embedding`, `tsv`. **Trabalho futuro**: na Fase 3 o corpus é só uma lista de referências (sem LLM nem embeddings); a pesquisa no texto integral fica para mais tarde, e só para documentos com licença.
- **ArchiveDoc**, **ArchiveChunk**: documentos aprovados da TUU, divididos por bloco (`block_key`). Na Fase 3, as MDJ/CTE de R1 e R2: o texto de cada bloco adaptativo, com os valores da ficha já em `{{v:…}}` e os dados pessoais mascarados; citado como `arc:<projeto>:<block_key>`.
- **CableDesignation** (dicionário de equivalências): `canonical` (ex.: `XZ1(frt,zh)`), `aliases[]` (as equivalências aprovadas), `kind` (fio | cabo), `flexible` (bool, ou desconhecido), `fire_class_default`, `status`/`reviewed_by`. **CableOccurrence**: cada designação tal como está escrita e onde (projeto, fonte, ficheiro, célula/linha/parágrafo, geometria). **CableEquivalence**: par proposto com a evidência (mesmo projeto, mesma secção e número de condutores, fontes diferentes); nunca rígido com flexível (-U/-K). As equivalências são **validadas pelo curador**; o agente pode propor, nunca aprovar.
- **TypologyLexicon** (implementado como **Typology** + **TypologyTerm**): tipologia (com a evidência da ficha e da capa) → termos incompatíveis (ex.: moradia unifamiliar ↛ "apartamento", "fração", "condóminos") e onde aparecem nos documentos de referência (C2), para a regra TIP-01. Tudo proposto até o curador decidir.

### 7.6 Equipamentos

- **Equipment** (biblioteca TUU): `category`, `manufacturer`, `model`, `reference`, `specialties[]`.
- **Datasheet**: `equipment_id`, `file_id`, `issue_date`, `language`, `status` (current | outdated).
- **EquipmentParam**: `datasheet_id`, `name` (chave normalizada, ex.: `ip_rating`, `ik_rating`, `detection_range_m`), `value`, `unit`, `page`, `review_status` (extracted | reviewed), `reviewed_by`.
- **Requirement** (do CTE): `document_id`, `block_key`, `equipment_category`, `param_name`, `operator` (= | ≥ | ≤ | in | ≥class), `value`, `unit`.
- **ProjectEquipment**: `ficha_value_id`, `equipment_id` (modelo de referência), `or_equivalent` (bool, sempre `true` por omissão nos CTE da TUU).
- A biblioteca inicial é semeada a partir dos equipamentos de referência dos CTE do arquivo (portinholas, quadros, tubos, caixas, aparelhagem, detetores de movimento, luminárias, módulos e inversores FV, carregadores VE, videoporteiro, elétrodos de terra), com as características que o CTE já lista.
- **Implementado (Fase 7, 0017)**, com estas diferenças:
  - `Equipment` também com `name` (como o CTE o descreve), `code` (tipo de luminária L1…, SNC, BS), `or_equivalent`,
    `sources` (projeto, bloco, entrada do bloco, linha do CTE, com os dados pessoais mascarados), `image` (a ilustração
    de um só projeto que o acompanha no CTE) e o estado de revisão do curador (proposto / aprovado / rejeitado).
  - `EquipmentParam` com `origin` (`cte`: o que o CTE diz do modelo de referência; `datasheet`: lido da ficha técnica)
    e o texto lido. Só os da ficha técnica **atual** contam na verificação.
  - `Datasheet` guarda o PDF no S3 (`equipment/<id>/datasheets/<uuid>`, SHA-256), as páginas, a data de emissão (lida
    junto de «Rev.», «edição», «data», «date», «fecha»… ou escrita pelo curador) e a língua; uma ficha nova passa a
    atual e a anterior a `outdated`.
  - `Requirement` pelo `block_key` do CTE (não por documento), da linha de um equipamento (`equipment_id`) ou do bloco
    inteiro; aprovado com o bloco pelo curador; operadores `>=`, `<=`, `=`, `>=class`, `info`.
  - `ProjectEquipment` por slot do CTE montado (secção, entrada do bloco, posição), com o equipamento de referência e o
    escolhido, a chave da ficha-base (`eq.*`, `sys.*`), quem escolheu e porquê.
  - Leitura sem LLM, pelos mesmos padrões no CTE e nas fichas (`app/equipment/params.py`): IP, IK, Icc (kA), W, kW,
    Wp, lm, K, V, alcance (m), ângulo (º), eficiência (%), autonomia (h), Euroclasse CPR e dimensões (só informação).

### 7.7 Transversal

- **AuditEvent** (só inserção): `actor_type` (agent | user | system), `actor_id`, `action`, `entity_type`, `entity_id`, `payload`, `at`.
- **LlmCall**: `purpose`, `provider`, `model`, `prompt_hash`, `input_tokens`, `output_tokens`, `cost_eur`, `latency_ms`, `status`.

---

## 8. Pipeline do agente

### 8.1 Visão geral

1. **Ingestão** dos ficheiros do projeto → valores candidatos com origem (8.2).
2. **Ficha-base**: consolidação; divergências entre fontes geram `FichaConflict`. A ficha tem de ser **confirmada por uma pessoa** antes de se montar qualquer peça.
3. **Montagem** de MDJ e CTE a partir da biblioteca de blocos, com as regras de ativação avaliadas sobre a ficha (8.3).
4. **Redação adaptativa** apenas dos blocos `adaptive` (8.4).
5. **Pré-preenchimento** dos formulários (8.5).
6. **Validação** cruzada de todas as peças do projeto (secção 9).
7. **Revisão humana** e **exportação**.

### 8.2 Ingestão

| Fonte | O que se extrai | Como |
|---|---|---|
| **Ficha eletrotécnica** (`.xlsm`, modelo DGEG) | Requerente, localização, caracterização do imóvel, tipo de instalação, entrada, potências | Leitura por **células fixas**, com um mapa por versão do modelo (`FE_v.20190222`: C5, Q5, J6, C7, C8, C15, M15, Q15, G16, Q16, F23, Q23, F24, Q24, linha 29 de B a R, bloco do técnico C11/Q11/C12/J12/Q12, potências por tipo I40/I42/I44, data M40, versão em R45; mapa confirmado com R1/R2). Se a versão em R45 for outra, a ingestão para e pede um novo mapa. Sem LLM. |
| **Tabela de Cálculo** (`.xlsx`, modelo TUU) | Um `Circuit` por linha: origem, destino, potência, IB, In, IΔn, Iz, I2, 1,45·Iz, cabo, comprimento, quedas de tensão, PdC, tipo de instalação | Deteção das colunas **pelo texto do cabeçalho** (não por posição: há colunas vazias, como IΔn). Secções "ENTRADA DE ENERGIA" e "EDIFÍCIO". Sem LLM. |
| **09-Folha de Cálculo** (`.xls`, uma por troço) | Valores de detalhe do troço: potência (`IB!H7`), IB (`IB!H17`), comprimento (`condutores!N8`), secção (`condutores!H47`), Iz corrigido (`proteccao!Z7`; `condutores!H52` é o Iz antes da correção), 1,45·Iz (`proteccao!U15`), queda de tensão do troço (`tensao!T12`, em fração), In (`proteccao!E9`), I2 (`proteccao!J9`) | Leitura por células com `xlrd` (`maps/folha09_tuu.yaml`, **[A CONFIRMAR] pela equipa**; modelo reconhecido pelas folhas e títulos, sem célula de versão). A folha não diz o troço: associa-se pelo nome do ficheiro (normalização dos nomes dos quadros, `boards.py`); sem correspondência única fica "por associar" e associa-se à mão. Compara-se com o `Circuit` à precisão do valor menos preciso ([A CONFIRMAR]); cada diferença é um `FichaConflict` no campo do troço. |
| **MQT / LPU** (`.xlsx`) | Capítulos, artigos, designações, unidades, quantidades e preços; identificação (designação, adjudicante) | MQT e LPU distinguem-se pelo **título** do documento. Deteção do cabeçalho (`CÓDIGO / DESIGNAÇÃO / UNI. / QUANT.` ou `Artº / Designação / Un / QUANTIDADES ADJUDICADAS` com a 2.ª linha `Quant. / Pr. Unit. / Total / Total Cap.`). Cada linha é um `BomItem`. **Fase 2: associação de artigos a chaves da ficha só por regras** (quadros pelo nome, portinhola, carregadores VE, módulos FV, luminárias pelo código L1…/SNC); os restantes associam-se à mão. *Trabalho futuro:* associação assistida pelo LLM, sempre confirmada por uma pessoa. |
| **PDF das peças desenhadas** | Índice de folhas (EL001…), carimbadura de cada página (requerente, projeto, especialidade, fase, data, código, código e título da folha) e número de páginas. *Trabalho futuro:* a legenda (tipos de tomadas e luminárias L1, L7…) | `pypdfium2`, só texto posicionado; páginas rodadas lidas como aparecem; texto espelhado e repetido descartado; a carimbadura é a faixa direita, com os valores alinhados pela coluna das etiquetas. Carimbaduras diferentes entre páginas → `FichaConflict`. A ficha mostra quando o índice e as folhas do PDF não coincidem (C4); a regra DES-01 é da Fase 5. **Os esquemas unifilares não se leem**: o texto sai sobreposto e ilegível. |
| **Arquivo DOCX** (MDJ/CTE aprovados) | Blocos e texto, para a biblioteca e para os blocos adaptativos | `python-docx`. Divisão pelos títulos de nível 1 (tabelas de 1 célula, ex.: "DIMENSIONAMENTO ELÉTRICO") e nível 2 (estilo `Heading 2`). |

### 8.3 Montagem por blocos

A análise dos projetos de referência mostra que o MDJ e o CTE seguem sempre o mesmo esqueleto, com blocos que só entram quando se aplicam. A montagem funciona assim:

| Modo | O que faz | LLM | Exemplos |
|---|---|---|---|
| `fixed` | Copia o bloco tal como está no modelo, incluindo OOXML (fórmulas, tabelas, imagens) | Não | Tabelas IP/IK, fórmulas de queda de tensão e curto-circuito, condições técnicas gerais, dúvidas e casos omissos |
| `parametric` | Preenche um texto-modelo com valores da ficha e condições simples | Não | Introdução, alimentação e potência, contagem, lista de quadros, esquema de ligação à terra, poder de corte, legislação aplicável |
| `adaptive` | Parte de um texto aprovado do arquivo e adapta-o ao projeto | Sim | Descrição da iluminação numa reabilitação, matriz de incêndio, descrição do sistema audiovisual |

**Esqueleto do MDJ de eletricidade** (a validar com a equipa; regra de ativação entre parênteses):

1. Capa (sempre) · 2. Introdução (sempre) · 3. Legislação e normas (sempre; itens condicionados aos blocos ativos, ex.: guia de VE só com `sys.ve`) · 4. Regulamento dos Produtos de Construção (`ele.classificacao` ≠ locais de habitação) · 5. Características dos equipamentos em função das influências externas (sempre) · 6. Classificação quanto à utilização do local (sempre) · 7. Instalação de alimentação, distribuição e medida: alimentação, contagem, distribuição (sempre) · 8. Dimensionamento elétrico: sobrecargas, quedas de tensão, curto-circuitos, poder de corte (sempre) · 9. Quadro elétrico (sempre) · 10. Canalizações: embebidas/ocultas (sempre), enterradas (existe `Circuit.installation = ENT` ou vala no MQT), proximidade (sempre) · 11. Caixas (sempre) · 12. Instalações a considerar: iluminação normal, iluminação de segurança (`sys.iluminacao_seguranca`), comandos (KNX se `sys.knx`), tomadas, alimentações específicas, esquema de ligação à terra (um subbloco por esquema em `ele.esquemas_terra`) · 13. SADI e matriz de incêndio (`sys.sadi`) · 14. Instalação fotovoltaica (`sys.fv`) · 15. Carregamento de veículos elétricos (`sys.ve`) · 16. Instalação audiovisual (`sys.audiovisual`) · 17. Proteção dos utilizadores: contactos diretos, contactos indiretos (texto depende dos esquemas de terra), terras e elétrodos, ligação equipotencial (sempre) · 18. Dúvidas e casos omissos (sempre) · 19. Local, data e identificação do técnico (sempre; data e assinatura pelo técnico).

**Esqueleto do CTE de eletricidade:** Condições técnicas gerais (introdução, materiais, ensaios de receção, omissões: `fixed`) · Condições técnicas especiais: entrada de energia · quadros elétricos · canalizações e tubos (VD, ERM, PEAD) · cabos e fios · caixas · aparelhagem, interruptores, tomadas e espelhos · detetores de movimento · iluminação normal (tipos L#) · iluminação de segurança · KNX (servidor, fonte, gateway DALI, atuadores, acoplador, sensores) · fotovoltaico (estrutura, módulos, inversor, medidor, contador) · SADI · carregamento de VE · audiovisual · videoporteiro · rede de terras, elétrodos, caixa de visita, condutores de proteção, ligações equipotenciais · dúvidas e casos omissos.

Nos blocos do CTE, os equipamentos de referência vêm da **biblioteca de equipamentos** (`equipment_slots`): o bloco escreve o modelo, as características e sempre "ou equivalente".

A biblioteca inicial de blocos é **extraída dos documentos de referência** (Fase 3): comparando MDJ e CTE de projetos diferentes, o texto igual passa a `fixed`, o texto que só muda em valores passa a `parametric` (com os valores trocados por `{{v:…}}`) e o resto fica como candidato a `adaptive`. O curador aprova cada bloco.

**Como foi feita a extração (Fase 3, `make seed-library`)** [A CONFIRMAR com o curador]:

- Cada documento é partido em capa (antes do índice), índice (a tabela «Conteúdo»), faixas de nível 1 (tabela de 1 linha e 2 células com texto), nível 2 (estilo «heading 2») e assinatura (de «Local, mês de ano» / «O Técnico» até ao fim). Os elementos do corpo ficam em OOXML tal como estão; o pacote do documento fica no S3.
- Os parágrafos são alinhados entre projetos (difflib e, dentro das zonas diferentes, parágrafos iguais sozinhos ou partidos em 2 a 4) depois de trocar os valores de cada projeto por `{{v:chave}}` no próprio OOXML (o valor fica na primeira run, com a sua formatação). Valores trocados: identificação (`id.*`), potências com «kVA», tensão com «kV»; capa e assinatura pelas etiquetas. As chaves de documento e do técnico (`doc.local`, `doc.data`, `tec.*`) são resolvidas na Fase 4.
- Igual nos dois → `fixed` (ou `parametric`, com os mesmos marcadores nos mesmos sítios); diferente → `adaptive` (texto para o arquivo); só num projeto → `parametric` com `single_source` quando tem valores da ficha, senão `adaptive`. Tabelas e imagens nunca são adaptativas. Um padrão de dado pessoal que sobre impede o modo fixo ou paramétrico. Capa e assinatura são sempre `parametric`. O bloco herda o modo mais forte dos seus parágrafos. Condições técnicas gerais do CTE: `fixed` (redação diferente fica com o texto de R1 e nota).
- Um teste falha se um bloco proposto tiver emails, NIF, CC, telefones, códigos postais, números DGEG/OET, moradas, datas, nomes do conjunto de pseudónimos ou valores das fichas de R1/R2 fora de `{{v:…}}`.

**Como se monta um documento (Fase 4, `POST /projects/{id}/documents`)** [A CONFIRMAR]:

- Só com a ficha-base **confirmada** (senão HTTP 409) e pelos papéis redator ou técnico. Usa os
  blocos na versão 1 que não foram rejeitados: um bloco proposto entra, mas a secção mostra
  «bloco não aprovado»; a exportação oficial (Fase 6) só aceita blocos aprovados e secções
  revistas (`export_readiness`, `GET /documents/{id}/export-check`).
- As regras de ativação são avaliadas sobre a ficha-base: uma secção desativada fica a cinzento,
  com a razão («desativada pela regra: …»), e só se ativa com justificação (auditoria).
- Fixos: nó bloqueado com o OOXML do bloco (editar exige desbloquear com justificação).
  Paramétricos: os marcadores resolvem-se com a ficha-base, os troços (`circ.<origem_destino>.<campo>`),
  os artigos (`bom.<código>.<campo>`) e o perfil do técnico (`tec.*`, `doc.local`); cada valor
  fica num `ValueRef`. Sem valor → secção `todo` «Falta dado: …». `doc.data` fica sempre vazio
  (P8: o técnico data). Adaptativos: `todo` «Por gerar», até o agente propor.
- Uma imagem que só existe num dos projetos de referência (em R1/R2: caixas e detetores de
  movimento) não é montada: é quase sempre um equipamento desse projeto; a secção diz porquê
  (a escolha é da Fase 7).
- **Rascunho .docx** (`GET /documents/{id}/draft.docx`): o pacote do MDJ/CTE de R1 como modelo
  provisório (até haver modelos TUU vazios); fixos e paramétricos com o OOXML original e os valores
  escritos na primeira run; adaptativos como parágrafos novos com as propriedades do parágrafo de
  origem; imagens e relações de R2 copiadas do S3; cabeçalho com `tec.nome` e mês/ano paramétricos;
  índice escrito a partir dos títulos da peça (as páginas, na exportação, pelo LibreOffice; sem ele, o Word
  atualiza-as ao abrir). Um paramétrico editado à mão exporta-se como texto com o
  estilo do parágrafo.
- A diferença para o original de R1 está em `docs/fase4-diff-R1.md` (`make diff-report`).

**Linguagem das regras de ativação** (texto curto, lido por um parser próprio, sem `eval`; guarda-se o texto e a árvore JSON; os erros dizem a posição):

```
regra    := or ;  or := and ("or" and)* ;  and := not ("and" not)* ;  not := "not" not | primário
primário := "(" regra ")" | "true" | "false" | chave ".present" | chave op literal
          | "any" ("circuit" | "bom") "." campo op literal
op       := == | != | ~ (contém) | in (lista) | > | < | >= | <=
```

`chave.present`: há valor na ficha ou um artigo do MQT/LPU associado a essa chave. `any bom.<designation|chapter|unit>` percorre os artigos (o capítulo é o do artigo). Texto comparado sem maiúsculas nem acentos; sem valor, a condição é falsa. Exemplos das regras propostas: RPC `ele.classificacao != "Locais de habitação"`; canalizações enterradas `any circuit.installation == "ENT" or any bom.designation ~ "abertura e tapamento de vala"`; FV `sys.fv.present`; SADI `any bom.chapter ~ "deteção de incêndio"`; KNX `any bom.designation ~ "KNX"`. Sobre R1 e R2, as regras reproduzem os blocos das MDJ e dos CTE, com as diferenças esperadas documentadas (C12: ENT em R2 sem canalizações enterradas; distribuição de energia só em R1; iluminação de segurança ativa sem bloco; espelhos só no CTE de R1). A lista completa para rever está em `docs/revisao-curador.md` (`make curator-review`).

### 8.4 Contrato de saída dos blocos adaptativos

O LLM devolve JSON validado por esquema. **Não escreve números, nomes nem valores do projeto**: usa `{{v:<chave>}}`, que o backend resolve.

```json
{
  "block_key": "ele.mdj.fotovoltaico",
  "paragraphs": [
    {
      "id": "p1",
      "text": "Foi projetada uma instalação fotovoltaica com potência nominal de {{v:sys.fv.potencia_kw}} kW, a instalar na cobertura, constituída por {{v:sys.fv.n_modulos}} módulos de {{v:sys.fv.modulo_wp}} Wp.",
      "sources": ["arc:R2:ele.mdj.fotovoltaico"]
    }
  ],
  "missing_data": ["sys.fv.strings"],
  "assumptions": ["Inversor na sala técnica dos quadros (texto de R2)."]
}
```

Regras de pós-processamento:

- Uma fonte que não esteja no conjunto fornecido na chamada é **removida** e gera `REF-01`.
- Um `{{v:…}}` sem valor confirmado fica marcado como "falta dado" e o bloco passa a `todo`.
- Qualquer algarismo fora de *placeholder* gera `NUM-01`, com uma lista branca configurável (números de secções e artigos, normas, edições e designações técnicas como "IP65", "H07V-U" ou "16A-250V").
- `missing_data` e `assumptions` aparecem ao técnico no painel lateral do editor.
- Prompts versionados em `backend/app/llm/prompts/` (`adaptive_block_v1`, `rewrite_v1`). Pedidos em linguagem natural no editor criam uma nova `SectionVersion` proposta, aceite ou rejeitada através do diff.
- O pedido (Fase 4) leva: as regras (sistema), o título e a tipologia do projeto, as fontes do
  arquivo do bloco (`arc:<projeto>:<chave>`, já com marcadores e sem dados pessoais), os parágrafos
  fixos da secção, as chaves disponíveis com etiqueta e unidade, os valores **não pessoais** da
  ficha como contexto e, num pedido em linguagem natural, o texto atual. A lista branca da NUM-01
  está em `backend/app/llm/whitelist.yaml` (normas, decretos, secções e artigos, IP/IK, designações
  de cabos, 230/400 V, «16A-250V»). Os números copiados das fontes (distâncias regulamentares)
  também geram NUM-01: ficam para o técnico confirmar.

### 8.5 Formulários

- **Ficha eletrotécnica**: escrita nas mesmas células fixas do modelo DGEG, a partir da ficha-base (inverso do mapa `fe_v20190222.yaml`) e do perfil do técnico (C11, Q11, C12, J12, Q12). As células são editadas no XML da folha (`app/forms/xlsx.py`), não com o `openpyxl`: este perderia as listas de validação DGEG e os controlos ActiveX. As macros (`vbaProject.bin`), os estilos e as fórmulas ficam iguais; as fórmulas recalculam ao abrir. A data (M40) e a assinatura ficam vazias. Circuito fechado: o leitor da Fase 1 lê de volta os valores da ficha-base.
- **Identificação do projeto** e **Termo de responsabilidade**: preenchidos com o `python-docx` (MIT) pelas etiquetas das tabelas do formulário DGEG («Nome:», «NIF:», «N.º OET:»…), por secção numerada; o `docxtpl` (LGPL) não é necessário. A data sai do texto da declaração; assinatura por fazer. O «X» de «Instalação nova/existente» do Termo vem de `ele.instalacao`; a secção 4 da Identificação fica para o técnico [A CONFIRMAR].
- **Modelos** (`backend/app/forms/templates/`): derivados dos formulários de R1 nas fixtures por `make form-templates`, com os valores do projeto apagados (células do mapa, técnico, data, resultados em cache das fórmulas, textos partilhados sem uso, ligações `mailto:`) [A CONFIRMAR até a TUU ter modelos vazios]. `make pii-check` também os verifica.
- API: `GET /projects/{id}/forms` (o que falta preencher à mão) e `GET /projects/{id}/forms/{kind}` (ficheiro; auditoria), só com a ficha-base confirmada. O perfil é o do técnico que confirmou a ficha-base (`GET/PUT /me/profile`, papel técnico).
- Os dados pessoais do técnico e do requerente só são inseridos neste passo, no backend, e nunca passam pelo LLM.
- **Na exportação (Fase 6)**, cada formulário só muda o que foi preenchido: na ficha eletrotécnica, só o XML da
  folha (as restantes partes, incluindo `vbaProject.bin`, `styles.xml`, `workbook.xml` e as validações de dados, ficam
  iguais byte a byte ao modelo; o fluxo comprimido do zip pode mudar, o conteúdo não); na identificação e no termo, só
  `word/document.xml`. No rascunho, a marca «RASCUNHO — não aprovado» vai no cabeçalho de impressão da folha
  (`<headerFooter>`) e nos cabeçalhos dos .docx. Nomes: `<CÓDIGO>_FichaEletrotecnica_<FASE>_ELE_V<n>.xlsm`,
  `<CÓDIGO>_IdentificacaoProjeto_…docx`, `<CÓDIGO>_TermoResponsabilidade_…docx` [A CONFIRMAR com a TUU].

---

## 9. Regras de validação (MVP)

As regras são módulos independentes (`backend/app/validation/rules/`), cada um com testes. A severidade por omissão é configurável. Cada regra tem pelo menos um caso de teste real no Anexo C (as que não têm estão em `docs/fase5-anexo-c.md`, com os testes que as cobrem).

Implementação (Fase 5): regras determinísticas, sem LLM, sobre factos extraídos de cada peça (`app/validation/extract/`): nas peças escritas, cada extrator só lê as secções do seu tema (potência nas de alimentação, carregadores na de veículos elétricos, quadros nas de quadros); números por extenso e uma única multiplicação escrita ("N pedestais com capacidade de M carregadores em cada"); cabos pelo localizador da Fase 3; capa e assinatura pelas etiquetas. O que não se lê com confiança fica "não comparável" (informação, com a razão). Os dados pessoais comparam-se no backend e a evidência sai mascarada (•••). Decisões por regra [A CONFIRMAR]:

- NUM-01 só no texto do agente (no texto humano os números são das pessoas); REF-01 no texto do agente é crítico, e uma citação do texto humano fora do corpus é aviso com pedido ao curador; REF-02: revogado é crítico, por confirmar pelo curador é uma informação por peça.
- COE-01: quadros, carregadores VE e módulos FV por quantidade; luminárias por tipo (o CTE lista os tipos L1, L7,
  SNC… sem quantidades: comparados com os artigos do MQT/LPU, as variantes L5.1/L5.2 como L5, aviso); a referência é a ficha-base e, sem valor, a fonte de onde a ficha o tira (Tabela, depois MQT/LPU); um texto que só nomeia quadros é comparável quando nomeia os mesmos; um valor da ficha editado à mão numa peça montada é COE-01.
- COE-03 e CNT-01 usam as regras de ativação do esqueleto 8.3 (regra "sempre" → CNT-01; regra que depende de um sistema → COE-03); a CNT-01 exige ainda que a MDJ indique a potência a alimentar (C6).
- COE-04: uma forma mais curta conta como igual (nome curto na capa, obra sem a designação completa); uma peça que difere em dois ou mais campos de identificação (ou os deixa vazios) é "reaproveitada de outro projeto" (C7); os dados do técnico comparam-se entre peças e a leitura é "Confirmar com o perfil do técnico" (C3).
- COE-06: a referência é a Tabela; MDJ e CTE comparam-se juntas e o MQT/LPU à parte; rígido vs flexível é crítico; sem equivalência aprovada, aviso e pedido ao curador; condutores de terra não se comparam.
- TIP-01: léxico da Fase 3, tipo de utilização contra a obra descrita (tabela de usos) e nomes de outros projetos do arquivo (excluindo a identificação do próprio projeto).
- CAL-01: queda de tensão total e poder de corte com os limites que a MDJ indica; os troços da Tabela são colunas montantes e comparam-se com o limite de "outros usos".

| ID | Categoria | Regra | Severidade |
|---|---|---|---|
| REF-01 | Referências | Citação ou fonte que não existe no corpus ou não foi fornecida | Crítico |
| REF-02 | Referências | Cita um documento revogado ou não citável | Crítico |
| REF-03 | Referências | Referência incompleta, ex.: "secção das RTIEBT" ou "secções da RTIEBT" sem número | Aviso |
| NUM-01 | Referências | Número no texto sem origem (fora de *placeholder* e da lista branca) | Crítico |
| COE-01 | Coerência | Quantidade de um elemento (quadros, carregadores, módulos, luminárias…) difere entre peças e ficha-base | Crítico se afetar MDJ ou CTE; aviso se afetar só o MQT |
| COE-02 | Coerência | Fonte com data posterior à ficha-base e que diverge dela → propor atualização da **ficha** (ficheiros pela data de carregamento; peças desenhadas pelo mês da carimbadura) | Aviso |
| COE-03 | Coerência | Sistema presente na ficha ou na Tabela de Cálculo sem bloco correspondente na MDJ ou no CTE, ou o inverso (ex.: troços `ENT` sem bloco de canalizações enterradas) | Aviso |
| COE-04 | Coerência | Identificação diferente entre peças: requerente, obra, localização, tipo de utilização ou dados do técnico (MDJ, CTE, MQT, ficha eletrotécnica, identificação, termo, carimbadura dos desenhos) | Crítico |
| COE-05 | Coerência | Potência instalada ou a alimentar diferente entre ficha eletrotécnica, identificação, MDJ, CTE e 1.ª linha da Tabela de Cálculo | Crítico |
| COE-06 | Coerência | Designação de cabos diferente entre MDJ, CTE, Tabela de Cálculo e MQT/LPU **depois de normalizada** pelo dicionário; designação desconhecida → pedir ao curador | Crítico se forem cabos diferentes (ex.: fio rígido vs flexível); aviso se a designação for desconhecida |
| TIP-01 | Coerência | Texto incompatível com a tipologia (ex.: "apartamento" numa moradia unifamiliar) ou nomes de outro projeto do arquivo (requerente, obra, morada) | Crítico |
| DES-01 | Peças desenhadas | O índice (EL001…) não corresponde às folhas do PDF (número ou códigos) | Aviso |
| CAL-01 | Cálculo (verificação) | Com os valores já existentes na Tabela de Cálculo: IB ≤ In ≤ Iz; I2 ≤ 1,45·Iz; queda de tensão total dentro dos limites indicados na MDJ (3% iluminação, 5% outros usos); PdC ≥ mínimo declarado na MDJ. O alerta mostra os valores e pede ao projetista que confirme na folha. **Não recalcula nada.** | Aviso |
| CCP-01 | Contratação | Marca ou modelo sem "ou equivalente" quando `public_procurement = true` | Aviso |
| CNT-01 | Conteúdo | Falta um bloco obrigatório do esqueleto | Aviso |
| TXT-01 | Qualidade | Quebras de linha a meio de frase, itens de lista repetidos, referências de produto duplicadas | Informação |
| EQP-01 | Fichas técnicas | Parâmetro da ficha técnica não cumpre o requisito do CTE (parâmetros só `reviewed`; os `extracted` geram aviso "confirmar parâmetro") | Crítico |
| EQP-02 | Fichas técnicas | Ficha técnica com mais de N anos (N = 3 por omissão) | Aviso |
| EQP-03 | Fichas técnicas | Equipamento de referência sem ficha técnica na biblioteca | Informação |

- Implementado (Fase 7): EQP-01 compara cada slot do CTE montado com os requisitos **aprovados** do bloco (do bloco
  inteiro e da linha do slot) e a ficha técnica atual do equipamento escolhido; um parâmetro revisto que falha é
  crítico, os só lidos dão um aviso «confirmar parâmetro», o que a ficha não diz é informação. EQP-02 com
  `EQUIPMENT_DATASHEET_MAX_AGE_YEARS` (3); uma ficha sem data é informação. EQP-03 uma vez por equipamento. As peças
  existentes (auditoria) não têm slots: R1 e R2 do Anexo C não mudam.

Cada alerta mostra o que foi encontrado, a evidência (excerto, valores comparados e origem), a leitura provável e as ações possíveis. **Nenhuma correção é aplicada sem clique humano.** "Ignorar" exige justificação.

A "leitura provável" é determinística: quando só uma peça difere da ficha-base, essa peça é a suspeita; quando a peça divergente é mais recente do que a ficha, a suspeita é a ficha.

---

## 10. Ecrãs e critérios de aceitação

Os ecrãs seguem o layout, os estados e as interações do mock-up, adaptados a instalações elétricas (quadros, potência, cabos, carregadores, FV em vez dos exemplos de ITED/SCIE).

**A aplicação começa vazia.** Tudo o que aparece nos ecrãs vem dos documentos carregados e das ações das pessoas; não há dados fictícios na interface. Cada ecrã tem um estado vazio que explica o que falta e oferece a ação seguinte (ex.: "Ainda não há projetos · Criar projeto"; na ficha, "Carregue a ficha eletrotécnica e a Tabela de Cálculo para criar a ficha-base"; na validação, "A validação fica disponível quando houver ficha-base confirmada e peças do projeto"). Os ecrãs que dependem de fases seguintes mostram o estado vazio e o que vão fazer, sem dados inventados.

### A · Painel
- Projetos e peças em curso, com estado (revisão *x/y*, alertas críticos) e responsável.
- ✅ Um alerta crítico novo aparece no painel sem ser preciso abrir a peça.
- Implementado (Fase 5): coluna "Validação" com os críticos abertos e os novos (não estavam na execução anterior), ligação ao ecrã E e total de críticos abertos.

### B · Novo projeto
- Assistente: Projeto → Âmbito → Ficheiros → Ficha-base → Montar.
- Carregamento de ficha eletrotécnica, Tabela de Cálculo, 09-Folhas de Cálculo, MQT/LPU e PDF das peças desenhadas, com resumo do que foi lido e avisos (ex.: "versão do modelo DGEG desconhecida", "3 designações de cabo desconhecidas").
- ✅ Não é possível montar peças sem ficha-base confirmada.

### C · Ficha do projeto
- Grupos da secção 7.2, com etiqueta de origem em cada valor (FICHA ELE, CÁLCULO, MQT, DES, MANUAL) e detalhe ao passar o rato (célula, linha, página).
- Tabela dos quadros e troços (a partir dos `Circuit`), com os valores da CAL-01 destacados quando falham.
- Dados pessoais mascarados por omissão, visíveis só para quem tem permissão.
- ✅ Alterar um valor numa nova revisão marca para rever todos os blocos que o usam.
- ✅ O agente nunca resolve um conflito por maioria ou por data.

### D · Editor assistido
- Três colunas: blocos com estado e modo (fixo, paramétrico, adaptativo) · documento · fontes e pedidos ao agente.
- Blocos `fixed` protegidos (`locked`); editá-los exige desbloqueio com justificação.
- Blocos desativados pela regra de ativação aparecem acinzentados, com a razão (ex.: "sem FV na ficha") e opção de ativar com justificação.
- ✅ Editar manualmente um valor que vem de *placeholder* pede confirmação e cria COE-01 se divergir da ficha.

### E · Validação
- Resumo, alertas com evidência e ações, e **matriz de coerência** do projeto: ficha-base como referência e colunas MDJ, CTE, MQT/LPU, Ficha ELE, Identificação/Termo, Tabela de Cálculo e Desenhos.
- Linhas mínimas da matriz: requerente, obra, localização, tipo de utilização, potência, n.º de quadros, cabos principais, n.º de carregadores VE, potência FV, dados do técnico.
- ✅ Com alertas críticos abertos, as peças não podem ser enviadas para revisão.
- Implementado (Fase 5): filtros por severidade, estado, regra e peça; evidência mascarada; ações "abrir no editor" (as peças existentes abrem só para leitura), "abrir na ficha", "pedir ao curador", "ignorar com justificação" (≥ 10 caracteres, na auditoria) e "reabrir"; `POST /projects/{id}/review-request` recusado (409) com críticos abertos, sem validação ou com uma validação em curso. Uma edição no editor pede uma revalidação das peças alteradas.

### F · Equipamentos
- Equipamentos de referência do CTE com modelo, data da ficha técnica e resultado da verificação.
- Detalhe por equipamento: parâmetro, exigido (bloco do CTE), valor da ficha (com página) e resultado; alternativas da biblioteca quando não cumpre.
- Biblioteca semeada a partir dos CTE de referência.
- ✅ Com `or_equivalent = true`, a verificação compara requisitos mínimos e nunca exige a marca.
- Implementado (Fase 7): uma linha por slot do CTE montado mais recente (quantidade do MQT/LPU: luminárias pelo
  código, o resto pelo artigo ligado à chave da ficha), modelo de referência, data da ficha e uma verificação que diz
  porquê («IP44 < IP55», «Ficha antiga», «Sem ficha»); o slot escolhido fica no endereço (`?slot=`). O redator e o
  técnico confirmam o modelo de referência (a sua ilustração entra no CTE) ou trocam por uma alternativa da mesma
  categoria, com justificação, na auditoria; só leitura para o curador e num CTE aprovado. Os alertas EQP abrem aqui.

### G · Base de conhecimento
- Corpus regulamentar, **biblioteca de blocos** (com modo, regra de ativação e versão), arquivo TUU, dicionário de cabos e léxico de tipologias.
- ✅ Só um curador pode aprovar blocos, equivalências de cabos e o estado `citable` de um documento.
- **Biblioteca de equipamentos** (Fase 7): por categoria, com a evidência do CTE, as fichas técnicas (carregar,
  data), os parâmetros lidos (rever, corrigir, acrescentar à mão), a verificação contra os requisitos dos blocos e
  aprovar/rejeitar; só o curador decide.

### H · Revisão e exportação
- Diff entre a proposta do agente e a edição do técnico, e da peça inteira entre uma revisão aprovada e o estado atual
  (secção a secção, com navegação pelas secções alteradas): componente `DiffView` (palavra a palavra, «A → B», número de
  alterações, «Alteração anterior/seguinte» pelo teclado, inserido/removido dito aos leitores de ecrã, dois temas).
- Cartão de aprovação com as condições reais (Fase 6, `app/review`): peça montada na aplicação; ficha-base confirmada e
  a mesma da peça; todas as secções ativas revistas; todos os blocos usados aprovados pelo curador (estado atual do
  bloco); validação sem alertas críticos. Cada condição falhada diz porquê, lista as secções e liga para onde se resolve.
- Técnico responsável (reatribuir com justificação), data do cabeçalho (opcional, só o técnico, P8), «Reabrir» com
  justificação e histórico de revisões (rev. A · V0 · R00, quem aprovou, porque se reabriu).
- Registo de auditoria cronológico que distingue o sistema, o agente e as pessoas.
- ✅ "Aprovar" só fica ativo quando todas as condições estão cumpridas.
- Exportação do **conjunto do projeto**: MDJ e CTE (`.docx`), ficha eletrotécnica (`.xlsm`), identificação e termo (`.docx`), com os nomes de ficheiro da convenção TUU (ex.: `<CÓDIGO>_MDJ_PE_ELE_V<n>.docx`).
  O **oficial** exige o MDJ e o CTE aprovados com todas as condições; até lá, só o **rascunho**, com a marca
  «RASCUNHO — não aprovado» em todas as páginas e no nome dos ficheiros (`<CÓDIGO>_MDJ_RASCUNHO-nao-aprovado.docx`).
  Lista das exportações anteriores, com o estado e a descarga.
- ✅ Na exportação, as etiquetas internas são removidas, os blocos `fixed` saem com o OOXML original e os formulários saem sem data nem assinatura.

---

## 11. Exportação

- Os modelos TUU (`.docx`) mantêm os estilos atuais: títulos de nível 1 como faixa numa tabela de 1 célula, `Heading 2`, `Estilo1`, `List Paragraph` e `Caption` ("Imagens meramente ilustrativas").
- A montagem junta os fragmentos OOXML dos blocos sobre o pacote do modelo (`app/assembly/docx.py`; até haver modelos
  TUU vazios, o pacote do MDJ/CTE de R1 [A CONFIRMAR]), preservando o OOXML dos blocos fixos (fórmulas e imagens).
  Uma entrada editada à mão sai como texto com o estilo do parágrafo de origem; os valores editados no texto
  adaptativo ficam editados; só os IDs repetidos (`wp:docPr`, marcadores) mudam.
- A capa e o bloco de assinatura usam os campos da ficha-base e do perfil do técnico. O cabeçalho é paramétrico:
  técnico do perfil, data só se o técnico a escreveu (P8), revisão `R<nn>`.
- Propriedades do documento: autor, «último a alterar» e empresa = TUU; título `<CÓDIGO> · <peça>`; nunca nomes de
  pessoas. Nada de `{{v:…}}`, marcas do editor nem `[falta: …]` no oficial (a exportação recusa e diz que valores
  faltam, só pelas etiquetas).
- **Índice**: as entradas saem dos títulos da própria peça (secções omitidas, novas ou editadas; numeração e
  marcadores `_Toc`), com o estilo das entradas do modelo; os números de página saem de um PDF do LibreOffice
  (com fontes métricas compatíveis: Carlito, Liberation) e o ficheiro já não pede ao Word para atualizar os campos.
- **Verificações automáticas** (`app/export/checks.py`), em cada exportação e nos testes: pacote (tipos de conteúdo,
  relações), IDs únicos, abre com o python-docx, estilos usados existem no modelo, imagens/fórmulas/tabelas iguais às
  secções de origem, LibreOffice converte (headless, na imagem do backend); .xlsm: todas as partes exceto a folha iguais
  ao modelo e releitura igual à ficha-base. O que só um humano vê está em `docs/fase6-verificacao-manual.md`.
- **Conjunto** (`app/export/bundle.py`, fila RQ `export`): .zip com os cinco ficheiros, PDF opcional de cada .docx
  (LibreOffice) e `manifesto.json` (peças, revisões, versões, quem aprovou e quando, avisos ignorados com
  justificação, o que falta preencher à mão, verificações, SHA-256). Cada ficheiro fica no S3 com o seu SHA-256
  (`projects/<id>/exports/<export>/<sha256>`) e a exportação aparece no registo de auditoria. Descarga: rascunho pelo
  redator e pelo técnico; oficial também pelo admin; nunca pelo curador.
- **TUU Maestro (D9)**: `GET /api/integration/projects/{code}/export` com `X-Service-Token` devolve o manifesto do último
  conjunto oficial e links assinados pela própria API (HMAC, `EXPORT_LINK_SECRET`, 24 h). Sem integração mais funda.

---

## 12. Segurança e dados

### 12.1 Geral

- SSO por OIDC; papéis verificados no backend em todos os endpoints.
- Alojamento na UE, cópias de segurança diárias, encriptação em repouso e em trânsito.
- LLM (Gemini API): chave de um **projeto Google da TUU**, nunca pessoal. Segundo os termos atuais, no EEE aplicam-se à quota gratuita as regras de tratamento de dados dos serviços pagos. A direção deve confirmar antes de se usarem dados reais **[A CONFIRMAR]**.
- Enviar ao LLM apenas o necessário (excertos de blocos, sem dados pessoais — P9).
- Segredos em variáveis de ambiente (`.env.example` sem valores). Auditoria só de inserção.

### 12.2 Dados pessoais e anonimização

Os documentos reais contêm dados pessoais do requerente e do técnico: nomes, NIF, n.º de CC, telefones, emails, moradas, coordenadas GPS e números DGEG/OET.

- **Script de anonimização** (`tools/anonymize.py`), a criar na Fase 0:
  - lê `.docx`, `.xls`, `.xlsx`, `.xlsm` e `.pdf` de `data/private/`;
  - substitui, de forma consistente em todo o projeto, nomes, NIF (9 dígitos), CC, telefones, moradas, códigos postais, coordenadas e números DGEG/OET por pseudónimos;
  - os emails **não** são substituídos (decisão de 24 set 2026): ficam nas fixtures tal como estão, e o que for enviado ao LLM a partir delas tem de os passar por *placeholder* (P9);
  - os nomes dos profissionais da equipa TUU (carimbaduras, campo "Equipa", formulários) **não** são tratados como dados pessoais nas fixtures (decisão de 24 set 2026): o anonimizador substitui-os onde os encontra, mas não tem de os encontrar todos; o que for enviado ao LLM a partir das fixtures passa-os também por *placeholder* (P9);
  - usa as células conhecidas da ficha eletrotécnica e das tabelas dos formulários para saber o que é pessoal, e expressões regulares para o resto do texto;
  - escreve os resultados em `data/fixtures/` e a tabela de correspondências em `data/private/` (nunca no Git);
  - falha se encontrar um padrão de dado pessoal que não conseguiu substituir.
- Os códigos dos projetos de referência no repositório são **R1** e **R2** (Anexo C).
- No produto, campos com `personal_data = true` estão mascarados na interface e nos registos da aplicação.

---

## 13. Design system (a partir do mock-up)

Os tokens abaixo são os do mock-up. Ficam em `frontend/src/styles/tokens.css` e são usados por todos os componentes. Não usar cores literais nos componentes.

```css
:root {
  --paper:#f4f2ec; --surface:#ffffff; --surface-2:#ebe8df; --sheet:#ffffff;
  --ink:#0a0a0a; --ink-2:#46443f; --ink-3:#77746b; --line:#dcd8cc; --line-2:#c9c4b5;
  --yellow:#ffd21e; --on-yellow:#0a0a0a; --hl:rgba(255,210,30,.34);
  --ok:#1d7447; --ok-bg:#e1f0e6; --warn:#9a5c00; --warn-bg:#fbedd2;
  --crit:#b3362a; --crit-bg:#f8e0dc; --info:#285686; --info-bg:#e0e9f3;
  --f-ui:"Archivo", system-ui, sans-serif;
  --f-doc:"Source Serif 4", Georgia, serif;
  --f-mono:"JetBrains Mono", ui-monospace, monospace;
}
/* Tema escuro: ver o bloco equivalente no mock-up (prefers-color-scheme + [data-theme]) */
```

Componentes base: `Pill`, `Chip`, `OriginTag` (FICHA ELE, CÁLCULO, MQT, DES, MANUAL), `Card`, `DataTable`, `StatusDot`, `BlockModeBadge` (fixo, paramétrico, adaptativo), `Button`, `SeverityStripe`, `DiffView`, `Timeline`, `Toast`, `MaskedValue` (dados pessoais).

Regras: o amarelo TUU é o acento e o marcador de "texto gerado por rever"; as cores semânticas são independentes do acento; foco visível, navegação por teclado e contraste AA nos dois temas.

---

## 14. Fases de desenvolvimento

No fim de cada fase: testes a passar, um commit por tarefa e `CLAUDE.md` atualizado.

| Fase | Entrega | Pronto quando |
|---|---|---|
| **0 · Base** | Monorepo, Docker Compose (Postgres + pgvector, Redis, S3), CI, `.env.example`, **script de anonimização** | `docker compose up` arranca tudo e o script de anonimização está testado. A anonimização de R1/R2 em `data/fixtures/` é pré-requisito dos leitores e testes da Fase 1 |
| **1 · Interface vazia e carregamento de documentos** | **Interface:** os 8 ecrãs do mock-up adaptados a eletricidade (secções 7.2, 8.3, 9, 10 e 13), cada um com estado vazio e sem dados inventados; os que dependem de fases seguintes (editor, validação, equipamentos, exportação) mostram o que vão fazer. **Backend mínimo:** modelos e migrações de `Project`, `ProjectFile`, `FichaRevision`, `FichaValue`, `FichaConflict`, `Circuit` e `AuditEvent` (7.1, 7.2, 7.7); criar e listar projetos, carregar ficheiros (S3, checksum, tipo detetado), consultar a ficha-base, resolver conflitos e confirmar revisões; ingestão em worker (RQ) com progresso por SSE; utilizador local de desenvolvimento com os papéis da secção 4 simulados (OIDC mais tarde, D6). **Leitores (sem LLM):** ficha eletrotécnica (células fixas, mapa por versão, para com aviso se R45 for desconhecida) e Tabela de Cálculo (um `Circuit` por linha, colunas pelo cabeçalho); cada valor com origem e `personal_data`; divergências criam `FichaConflict`. **Ecrã C com dados reais:** grupos 7.2, etiquetas de origem, dados pessoais mascarados, tabela de troços com a CAL-01 destacada, resolução de conflitos e confirmação da revisão na auditoria | Com R1 e R2 anonimizados: a potência de R1 coincide entre as fontes (controlo do Anexo C) e a divergência de R2 (C6) aparece como `FichaConflict`; percurso Playwright criar projeto → carregar os dois ficheiros de R2 → ver a ficha → resolver o conflito de potência → confirmar a revisão, com capturas em tema claro, escuro e telemóvel; dois temas, 400 px sem scroll horizontal, navegação por teclado, sem erros graves no `@axe-core/playwright`; `make test` e `make e2e` verdes |
| **2 · Restantes leitores** ✅ (25 set 2026) | Leitores das 09-Folhas de Cálculo, MQT/LPU e PDF das peças desenhadas (secção 8.2), ligados à ficha-base com origem e conflitos; associação de 09-Folhas e de artigos por regras e à mão; ecrãs B e C com os novos tipos | As fichas-base de R1 e R2 incluem os valores destas fontes, com os conflitos reais do Anexo C a aparecer como `FichaConflict`: C7 (requerente da ficha ≠ adjudicante da LPU), C4 visível na ficha (índice de R1 com 17 folhas, PDF com 16); controlos sem alertas (quadros do MQT de R1 = Tabela; 09-Folhas de R1 = Tabela, exceto a queda de tensão de Q.E.G. → Q.P.1.2, decidida como divergência real); percurso Playwright com o conjunto completo de R2 |
| **3 · Biblioteca de blocos e conhecimento** · implementada (25 set 2026), à espera do curador (D7) | Extração de blocos a partir dos MDJ/CTE de R1 e R2, aprovação pelo curador, corpus regulamentar, dicionário de cabos, léxico de tipologias. Feito: 42 blocos do MDJ e 53 do CTE propostos, com OOXML, evidência e regras; dicionário, léxico e corpus (só referências) propostos; ecrã do curador | Os esqueletos da secção 8.3 estão completos com blocos aprovados e regras de ativação (a aprovação é do curador: `docs/revisao-curador.md`) |
| **4 · Montagem e redação** · implementada (28 set 2026) | Montagem `fixed`/`parametric`, redação `adaptive`, editor TipTap com blocos protegidos, pré-preenchimento dos formulários. Feito: montagem com a biblioteca proposta («bloco não aprovado»), rascunho .docx, camada de LLM com D5, guarda de privacidade e ritmo, propostas do agente em diff, ecrã D, perfil do técnico cifrado, FE/Identificação/Termo; `docs/fase4-diff-R1.md` sem defeitos | O MDJ e o CTE de R1 são montados a partir da ficha-base, e a diferença para o original aprovado é só texto adaptativo e correções de incoerências |
| **5 · Validação** · implementada (28 set 2026) | Regras da secção 9 e matriz de coerência do projeto. Feito: motor em worker com revalidação das peças alteradas, peças existentes (modo auditoria), extração de factos sem LLM, 16 regras (EQP-* na Fase 7), ecrã E com matriz, bloqueio do envio para revisão, painel; `docs/fase5-anexo-c.md` | Todos os casos do Anexo C são detetados, com a leitura provável correta (14/14 em R1 e R2 carregados como auditoria; controlos sem alertas) |
| **6 · Revisão e exportação** · implementada (6 out 2026) | Diff, aprovação, exportação do conjunto do projeto. Feito: técnico responsável atribuído, aprovação com as condições reais e revisões (rev. A → B, V0 → V1), DiffView e diff entre revisões, valores manuais na ficha-base, .docx oficial e rascunho com marca de água, formulários com os pacotes intactos, conjunto .zip com manifesto, PDF por LibreOffice, endpoint D9, ecrã H; verificações de fidelidade automáticas | O conjunto de R1 exporta e abre no Word/Excel com os estilos e macros intactos |
| **7 · Equipamentos** · implementada (7 out 2026) | Biblioteca semeada a partir dos CTE, fichas técnicas, requisitos, regras EQP. Feito: 77 equipamentos e 87 requisitos propostos de R1/R2, leitura das fichas sem LLM, revisão do curador, slots do CTE com alternativas e ilustração, EQP-01/02/03, ecrãs F e G | Os equipamentos de referência de R1 têm ficha técnica associada e verificada: **em parte** (8 out 2026): 20 de 32 com a ficha do fabricante, nenhum falha o CTE (`docs/fase7-fichas-R1.md`); faltam 12 fichas (`data/fixtures/fichas-tecnicas/R1/fichas.json`) e a revisão do curador |
| **8 · Piloto** | Três projetos reais de eletricidade feitos no Maestro Especiais | Tempos medidos e comparados com o processo atual |
| **9 · Especialidades seguintes** | ITED, depois SCIE/segurança | Biblioteca de blocos e ficha-base da nova especialidade aprovadas |

---

## 15. Dados de teste

### 15.1 Já disponíveis

- **R1**: moradia unifamiliar, projeto de execução de eletricidade (MDJ, CTE, MQT, ficha eletrotécnica, identificação, termo, 09-Folhas, Tabela de Cálculo, DWG e PDF das peças desenhadas).
- **R2**: reabilitação de biblioteca municipal, projeto de execução de eletricidade com FV, VE, SADI, KNX, UPS e audiovisual (MDJ, CTE, LPU, ficha eletrotécnica, 09-Folhas, Tabela de Cálculo, DWG e PDF das peças desenhadas).
- Nota: alguns ficheiros vieram corrompidos no arquivo `.rar` de R2 (duas 09-Folhas, as exportações Hager) e de R1 (um DWG antigo e um PDF assinado). Pedir novas cópias se forem precisos.

### 15.2 A pedir à equipa

- [ ] 3 a 5 conjuntos de eletricidade aprovados (idealmente tipologias diferentes: habitação coletiva, comércio, serviços).
- [ ] Modelos `.docx` TUU **vazios** do MDJ e do CTE, e os modelos dos formulários.
- [ ] Confirmação do mapa de células das 09-Folhas e da Tabela de Cálculo (e se os modelos têm versões).
- [ ] Lista do corpus regulamentar a incluir, validada por um técnico (ver Anexo D).
- [ ] Tabela de equivalências de designações de cabos usada pela equipa.
- [ ] Fichas técnicas dos equipamentos de referência mais usados (Fase 7: primeiro as de R1, em `data/fixtures/fichas-tecnicas/`, PDF dos fabricantes, sem anonimização; fecham o critério da Fase 7).
- [ ] Outros casos de erro conhecidos, para testes de regressão.

---

## 16. Decisões em aberto

| # | Decisão | Recomendação | Responsável |
|---|---|---|---|
| D1 | Stack do backend | Python (FastAPI) | Equipa técnica |
| D2 | Base de dados | PostgreSQL + pgvector | Equipa técnica |
| D3 | Embeddings | ✅ Decidido: modelo de embeddings do Gemini | — |
| D4 | Alojamento | Cloud na UE para o piloto. **8 out 2026: por agora, só no PC do utilizador** | Direção |
| D5 | Termos de tratamento de dados da Gemini API | Confirmar a aplicação das regras de serviço pago no EEE; ponderar plano pago no piloto. **✅ 8 out 2026: aceite (Gemini, Groq e Claude); o LLM fica ligado por omissão** | Direção |
| D6 | Autenticação | Microsoft Entra ID, se aplicável. **8 out 2026: até lá, contas com email e password (`make create-user`), cookie de sessão assinado** | TI |
| D7 | Curador do corpus, blocos e dicionários | Um técnico sénior de eletricidade, ~2 h/mês. **8 out 2026: provisório, as propostas dão-se como boas e corrigem-se nos testes; aprovar continua a ser humano** | Coordenação |
| D8 | Esqueletos e blocos obrigatórios (CNT-01) | Validar a secção 8.3 com a equipa. **8 out 2026: aceites como estão; corrigem-se nos testes** | Técnicos |
| D9 | Integração com o TUU Maestro | Endpoint de exportação no MVP | Equipa TUU Maestro |
| D10 | LLM | ✅ Decidido: Gemini Flash (quota gratuita) no desenvolvimento; desde 8 out 2026 também Groq e Claude, principal escolhido pelo admin | — |
| D11 | Especialidade do MVP | ✅ Decidido: instalações elétricas (ITED na Fase 9) | — |
| D12 | Leitura de DWG (fase posterior) | Avaliar conversor DWG→DXF e respetiva licença | Equipa técnica |
| D13 | Severidade da CAL-01 | Aviso, com confirmação do projetista na folha | Técnicos |

---

## 17. Como trabalhar com o Claude Code

- Comece cada fase com: *"Lê `docs/SPEC.md` e `CLAUDE.md`. Vamos implementar a Fase N. Entra em plan mode e propõe um plano com tarefas pequenas, testes e ficheiros afetados."*
- Reveja o plano antes de aprovar. Peça alterações se algo contrariar os princípios da secção 3.
- Uma tarefa, um commit. Testes sempre junto com o código.
- Nunca dê ao Claude Code os ficheiros de `data/private/`: trabalhe só com `data/fixtures/`.
- Quando uma decisão da secção 16 for tomada, atualize este documento e o `CLAUDE.md`.

**Primeira mensagem sugerida (Fase 0):**

> Lê `docs/SPEC.md` e `CLAUDE.md`. Vamos começar pela Fase 0: estrutura do monorepo, Docker Compose, CI e o script de anonimização da secção 12.2. Os ficheiros reais estão em `data/private/R1` e `data/private/R2` e não podem ser lidos por ti diretamente: escreve o script e os testes com ficheiros sintéticos, e eu corro-o localmente. Entra em plan mode e espera pela minha aprovação.

---

## Anexo A · `CLAUDE.md` inicial

Copiar para a raiz do repositório.

```markdown
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

## Convenções
- UI em PT-PT. Código, tabelas, endpoints e commits em inglês.
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

## Comandos
- docker compose up          # ambiente completo
- make test                  # pytest + vitest
- make e2e                   # Playwright
- make anonymize             # corre tools/anonymize.py (local, fora do Git)

## Dados
- data/fixtures/ : R1 e R2 anonimizados (versionados)
- data/private/  : originais e tabela de correspondências (NUNCA versionar)

## Estado atual
- Fase: 0
- Decisões tomadas: D3 (embeddings Gemini), D10 (Gemini Flash), D11 (MVP em eletricidade)
```

---

## Anexo B · Glossário

| Termo | Significado |
|---|---|
| MDJ | Memória descritiva e justificativa |
| CTE | Condições técnicas (gerais e especiais) do caderno de encargos |
| MQT / LPU | Mapa de quantidades de trabalhos / lista de preços unitários |
| Ficha eletrotécnica | Formulário da DGEG que caracteriza a instalação elétrica de serviço particular |
| Ficha-base | Dados principais do projeto, versionados e confirmados, usados como fonte de verdade |
| RTIEBT | Regras Técnicas das Instalações Elétricas de Baixa Tensão (Portaria n.º 949-A/2006, na redação atual) |
| DGEG / E-REDES / RESP | Direção-Geral de Energia e Geologia / operador da rede de distribuição / rede elétrica de serviço público |
| OET / OE | Ordem dos Engenheiros Técnicos / Ordem dos Engenheiros |
| Tipo A / B / C | Classificação das instalações: geradores de segurança e socorro / alimentadas em MT/AT/MAT / alimentadas em BT |
| Q.E.G. / Q.P. | Quadro elétrico geral / quadro parcial |
| PBT / portinhola | Caixa de entrada da alimentação em BT |
| IB, In, Iz, I2 | Corrente de serviço, corrente estipulada da proteção, corrente admissível na canalização, corrente convencional de funcionamento |
| QDT | Queda de tensão |
| PdC | Poder de corte |
| TT / IT / TN | Esquemas de ligação à terra |
| RPC / CPR | Regulamento dos Produtos de Construção (classes de reação ao fogo dos cabos) |
| NIP / CPE | Número de identificação do prédio / código do ponto de entrega |
| FV / VE / UPS | Fotovoltaico / veículos elétricos / fonte de alimentação ininterrupta |
| SADI / CDI | Sistema automático de deteção de incêndio / central de deteção de incêndio |
| KNX / DALI | Protocolos de automação de edifícios e de controlo de iluminação |
| Bloco fixo / paramétrico / adaptativo | Modos de montagem da secção 8.3 |
| Placeholder | Marcador `{{v:chave}}` que o backend substitui por um valor com origem |

---

## Anexo C · Casos de teste reais (R1 e R2)

Incoerências encontradas nos projetos de referência. Cada uma tem de ser detetada pela regra indicada, com a leitura provável indicada. Não contêm dados pessoais.

| # | Projeto | O que acontece | Regra | Leitura provável esperada |
|---|---|---|---|---|
| C1 | R1 | MDJ indica fios H07V-K; CTE e Tabela de Cálculo indicam H07V-U | COE-06 | Erro provável na MDJ |
| C2 | R1 | O CTE (videoporteiro) refere "ecrã na entrada de cada apartamento" numa moradia unifamiliar | TIP-01 | Texto herdado de outro projeto |
| C3 | R1 | O n.º de membro OET do técnico difere entre MDJ/CTE e identificação/termo | COE-04 | Confirmar com o perfil do técnico |
| C4 | R1 | O índice das peças desenhadas lista 17 folhas (EL001–EL017) e o PDF tem 16 páginas | DES-01 | Folha em falta no PDF ou índice desatualizado |
| C5 | R1 | Videoporteiro com modelo de marca sem "ou equivalente"; referência de comutador repetida | CCP-01 (se aplicável), TXT-01 | — |
| C6 | R2 | Potência: ficha eletrotécnica 180 kVA; CTE e Tabela de Cálculo 200 kVA; MDJ sem valor | COE-05, CNT-01 | Erro provável na ficha eletrotécnica |
| C7 | R2 | A ficha eletrotécnica tem outro requerente (não o da MDJ/CTE/LPU), tipo de utilização "Escritório" e rua/freguesia vazias | COE-04, TIP-01 | Ficha reaproveitada de outro projeto |
| C8 | R2 | Carregadores VE: MDJ e Tabela de Cálculo 5; CTE descreve 3 pedestais com 2 carregadores cada (6) | COE-01 | Erro provável no CTE |
| C9 | R2 | Cabos: "FXZ1" (MDJ/CTE), "RZ1-K (AS)" (Tabela de Cálculo), "XZ1(frt,zh)" (LPU) | COE-06 | Pedir equivalência ao curador |
| C10 | R2 | Troço Portinhola → Q.E.G.: I2 = 504 A e 1,45·Iz = 503,4 A na Tabela de Cálculo | CAL-01 | Confirmar na folha de cálculo |
| C11 | R2 | "Segundo a secção das RTIEBT" e "secções da RTIEBT" sem número | REF-03 | — |
| C12 | R2 | Tabela de Cálculo com troços enterrados (`ENT`: carregadores VE, UPS) e MDJ sem bloco de canalizações enterradas | COE-03 | Bloco em falta na MDJ |
| C13 | R2 | Parágrafos da MDJ com quebras de linha a meio de frase | TXT-01 | — |
| C14 | R1 | Duas entradas quase iguais sobre normas portuguesas na lista de legislação e normas da MDJ | TXT-01 (itens quase duplicados) | — |

Casos de controlo (não podem gerar alertas): em R1, a potência (34,5 kVA) coincide entre ficha eletrotécnica, identificação, MDJ e Tabela de Cálculo, e o número de quadros (6) coincide entre MDJ, CTE, MQT e Tabela de Cálculo.

---

## Anexo D · Referências encontradas nos documentos de referência

Ponto de partida para o corpus. **O curador confirma a edição em vigor de cada uma antes de a marcar como `citable`.**

- RTIEBT – Portaria n.º 949-A/2006, na redação atual
- Decreto-Lei n.º 96/2017 (instalações elétricas de serviço particular: termo de responsabilidade e identificação do projeto)
- Despacho n.º 1/2018 da DGEG (classificação das instalações usada na ficha eletrotécnica)
- Guia Técnico das Instalações Elétricas para carregamento de VE (DGEG)
- Guia Técnico das classes de reação ao fogo dos cabos elétricos (RPC)
- Especificações da E-REDES (ex.: elétrodos de terra, DMA-C65-210/N)
- NP EN 60529 (códigos IP) · NP EN 50102 (códigos IK) · EN 60898 (disjuntores) · NP EN 61386 (tubos) · EN 50086-2-4 (tubos enterrados) · EN 12464-1 (iluminação de locais de trabalho) · HD 602 / HD 606 (comportamento dos cabos em incêndio)
- Portaria n.º 701-H/2008 (conteúdo dos projetos)
