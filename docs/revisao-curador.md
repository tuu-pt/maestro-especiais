# Revisão do curador · Fase 3

Gerado a partir das propostas da biblioteca (`make seed-library` e depois `make curator-review`). **Nada está aprovado**: tudo o que o agente extraiu dos projetos de referência R1 e R2 (anonimizados) fica «proposto» até o curador decidir no ecrã G · Base de conhecimento, com o papel Curador. Cada decisão fica na auditoria.

O curador ainda não está designado (D7). Sem ele, a Fase 3 não fecha: o critério da SPEC 14 pede os esqueletos da secção 8.3 completos com blocos **aprovados**.

## Como rever

1. Ecrã G → Biblioteca de blocos: para cada bloco, ver os parágrafos (marcadores `{{v:…}}` realçados), a evidência de R1 e R2 lado a lado, a regra de ativação e a pré-visualização com a ficha de um projeto. Aprovar, editar (título, modo, regra, com justificação) ou rejeitar.
2. Dicionário de cabos, Léxico de tipologias e Corpus regulamentar: aprovar ou rejeitar cada proposta; no corpus, confirmar o estado e a edição em vigor antes de marcar como citável.
3. As decisões de método abaixo (marcadas [A CONFIRMAR]) valem para todos os blocos.

## Decisões de método [A CONFIRMAR]

- O modo de um bloco é o mais forte dos seus parágrafos (adaptativo > paramétrico > fixo).
- Um marcador `{{v:chave}}` só é proposto quando R1 e R2 coincidem com a mesma chave no mesmo sítio; um parágrafo que só existe num projeto e tem valores da ficha fica paramétrico com a marca «evidência de um só projeto» (ex.: a potência de R1).
- Valores trocados por marcadores: identificação (`id.*`), potências com «kVA» e tensão com «kV»; da capa e da assinatura, pelas etiquetas (requerente, localização, obra; local, data, técnico). Os valores das listas DGEG («Habitação», «Nova»…) ficam como texto: servem as regras.
- Chaves novas, fora da ficha, resolvidas na Fase 4: `doc.local`, `doc.data` (vazio, P8), `tec.nome`, `tec.titulo`, `tec.cc`, `tec.oet`, `tec.codigo_verificacao`, `tec.email`, `tec.telefone`.
- Tabelas e imagens (as fórmulas são imagens) nunca são adaptativas: quando diferem, fica a de R1 como fixa, com nota.
- O mesmo texto partido noutros parágrafos, ou com outra pontuação final, conta como igual.
- Condições técnicas gerais do CTE propostas como fixas: redação diferente fica com o texto de R1 e nota; só o parágrafo que identifica o projeto fica adaptativo.
- O cabeçalho dos documentos tem o técnico, a data e a revisão: fica no pacote do documento de origem e terá de ser paramétrico na Fase 4.
- Blocos adaptativos: o texto de cada projeto vai para o arquivo (marcadores no lugar dos valores, dados pessoais mascarados); o bloco guarda só a regra e as referências.
- Equivalências de cabos só com evidência: mesmo projeto, mesma secção e número de condutores, fontes diferentes.

## Biblioteca de blocos · MDJ

42 blocos: 16 fixos, 2 paramétricos, 24 adaptativos. Estado: 42 proposto.

| # | Bloco | Modo | Projetos | Regra de ativação | Estado |
|---|---|---|---|---|---|
| 1 | Capa | paramétrico | R1, R2 | `true` | proposto |
| 2 | Índice | fixo | R1, R2 | `true` | proposto |
| 3 | INTRODUÇÃO | adaptativo | R1, R2 | `true` | proposto |
| 4 | LEGISLAÇÃO E NORMAS | fixo | R1, R2 | `true` | proposto |
| 5 | REGULAMENTO DOS PRODUTOS DE CONSTRUÇÃO (RPC) | adaptativo | R2 | `ele.classificacao != "Locais de habitação"` | proposto |
| 6 | CARACTERÍSTICAS DOS EQUIPAMENTOS EM FUNÇÃO DAS INFLUÊNCIAS EXTERNAS | fixo | R1, R2 | `true` | proposto |
| 7 | CLASSIFICAÇÃO QUANTO À UTILIZAÇÃO DO LOCAL | adaptativo | R1, R2 | `true` | proposto |
| 8 | INSTALAÇÃO DE ALIMENTAÇÃO, DISTRIBUIÇÃO E MEDIDA DE ENERGIA | fixo | R1, R2 | `true` | proposto |
| 9 | ↳ Alimentação de Energia | adaptativo | R1, R2 | `true` | proposto |
| 10 | ↳ Contagem | adaptativo | R1, R2 | `true` | proposto |
| 11 | ↳ Distribuição de Energia | adaptativo | R1 | `true` | proposto |
| 12 | DIMENSIONAMENTO ELÉTRICO | fixo | R1, R2 | `true` | proposto |
| 13 | ↳ Contra Sobrecargas | fixo | R1, R2 | `true` | proposto |
| 14 | ↳ Quedas de Tensão | fixo | R1, R2 | `true` | proposto |
| 15 | ↳ Contra Curto-Circuitos | fixo | R1, R2 | `true` | proposto |
| 16 | ↳ Poder de Corte dos Aparelhos de Proteção | fixo | R1, R2 | `true` | proposto |
| 17 | QUADRO ELÉTRICO | adaptativo | R1, R2 | `true` | proposto |
| 18 | CANALIZAÇÕES | adaptativo | R1, R2 | `true` | proposto |
| 19 | ↳ Canalizações Embebidas ou Ocultas | adaptativo | R1, R2 | `true` | proposto |
| 20 | ↳ Canalizações Enterradas | adaptativo | R1 | `any circuit.installation == "ENT" or any bom.designation ~ "abertura e tapamento de vala"` | proposto |
| 21 | ↳ Proximidade com Outras Canalizações | fixo | R1, R2 | `true` | proposto |
| 22 | CAIXAS | adaptativo | R1, R2 | `true` | proposto |
| 23 | INSTALAÇÕES ELÉTRICAS A CONSIDERAR | adaptativo | R1, R2 | `true` | proposto |
| 24 | ↳ Iluminação Normal | adaptativo | R1, R2 | `true` | proposto |
| 25 | ↳ Iluminação de Segurança | adaptativo | esqueleto 8.3 | `sys.iluminacao_seguranca.present or any bom.designation ~ "iluminação de segurança"` | proposto |
| 26 | ↳ Comandos de Iluminação | adaptativo | R1, R2 | `true` | proposto |
| 27 | ↳ Tomadas de Usos Gerais | adaptativo | R1, R2 | `true` | proposto |
| 28 | ↳ Alimentações Específicas | fixo | R1, R2 | `true` | proposto |
| 29 | ↳ Esquema de Ligação à Terra | adaptativo | R1, R2 | `true` | proposto |
| 30 | SISTEMA AUTOMÁTICO DE DETEÇÃO DE INCÊNDIO (SADI) | fixo | R2 | `any bom.chapter ~ "deteção de incêndio"` | proposto |
| 31 | ↳ SADI | adaptativo | R2 | `any bom.chapter ~ "deteção de incêndio"` | proposto |
| 32 | ↳ Matriz de Incêndio | adaptativo | R2 | `any bom.chapter ~ "deteção de incêndio"` | proposto |
| 33 | INSTALAÇÃO FOTOVOLTAICA | adaptativo | R2 | `sys.fv.present` | proposto |
| 34 | CARREGAMENTO DE VEÍCULOS ELÉTRICOS | adaptativo | R2 | `sys.ve.present` | proposto |
| 35 | INSTALAÇÃO AUDIOVISUAL - AUDITÓRIO | adaptativo | R2 | `any bom.chapter ~ "audiovisual"` | proposto |
| 36 | PROTEÇÃO DOS UTILIZADORES | fixo | R1, R2 | `true` | proposto |
| 37 | ↳ Proteção Contra Contatos Diretos | fixo | R1, R2 | `true` | proposto |
| 38 | ↳ Proteção Contra Contatos Indiretos | adaptativo | R1, R2 | `true` | proposto |
| 39 | ↳ Circuito de Terras e Elétrodos de Terra | adaptativo | R1, R2 | `true` | proposto |
| 40 | ↳ Ligação Equipotencial | fixo | R1, R2 | `true` | proposto |
| 41 | DÚVIDAS E CASOS OMISSOS | fixo | R1, R2 | `true` | proposto |
| 42 | Local, data e técnico | paramétrico | R1, R2 | `true` | proposto |

#### O que pedir atenção no MDJ

- **Índice** (`ele.mdj.indice`)
  - Índice: o Word atualiza-o ao abrir.
- **INTRODUÇÃO** (`ele.mdj.introducao`)
  - Texto diferente em R1 e R2.
- **REGULAMENTO DOS PRODUTOS DE CONSTRUÇÃO (RPC)** (`ele.mdj.regulamento_dos_produtos_de_construcao_rpc`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
- **CARACTERÍSTICAS DOS EQUIPAMENTOS EM FUNÇÃO DAS INFLUÊNCIAS EXTERNAS** (`ele.mdj.caracteristicas_dos_equipamentos_em_funcao_das_influencias_externas`)
  - Diferente em R2: fica a de R1 (a confirmar).
- **CLASSIFICAÇÃO QUANTO À UTILIZAÇÃO DO LOCAL** (`ele.mdj.classificacao_quanto_a_utilizacao_do_local`)
  - Texto diferente em R1 e R2.
- **Alimentação de Energia** (`ele.mdj.instalacao_de_alimentacao_distribuicao_e_medida_de_energia.alimentacao_de_energia`)
  - Texto diferente em R1 e R2.
  - Só em R1: os valores da ficha foram trocados por marcadores, com evidência de um só projeto.
  - Paramétrico com evidência de um só projeto: `{{v:ele.potencia_alimentar_kva}}` (Potência a alimentar).
- **Contagem** (`ele.mdj.instalacao_de_alimentacao_distribuicao_e_medida_de_energia.contagem`)
  - Texto diferente em R1 e R2.
- **Distribuição de Energia** (`ele.mdj.instalacao_de_alimentacao_distribuicao_e_medida_de_energia.distribuicao_de_energia`)
  - Bloco só em R1: candidato, a regra de ativação decide.
  - Só em R1.
- **QUADRO ELÉTRICO** (`ele.mdj.quadro_eletrico`)
  - Texto diferente em R1 e R2.
- **CANALIZAÇÕES** (`ele.mdj.canalizacoes`)
  - Texto diferente em R1 e R2.
- **Canalizações Embebidas ou Ocultas** (`ele.mdj.canalizacoes.canalizacoes_embebidas_ou_ocultas`)
  - Texto diferente em R1 e R2.
- **Canalizações Enterradas** (`ele.mdj.canalizacoes.canalizacoes_enterradas`)
  - Bloco só em R1: candidato, a regra de ativação decide.
  - Só em R1.
- **CAIXAS** (`ele.mdj.caixas`)
  - Só em R1.
- **INSTALAÇÕES ELÉTRICAS A CONSIDERAR** (`ele.mdj.instalacoes_eletricas_a_considerar`)
  - Só em R1.
  - Só em R2.
- **Iluminação Normal** (`ele.mdj.instalacoes_eletricas_a_considerar.iluminacao_normal`)
  - Texto diferente em R1 e R2.
  - Só em R2.
- **Iluminação de Segurança** (`ele.mdj.instalacoes_eletricas_a_considerar.iluminacao_de_seguranca`)
  - Esqueleto 8.3: nenhum projeto de referência tem este bloco; falta o texto.
- **Comandos de Iluminação** (`ele.mdj.instalacoes_eletricas_a_considerar.comandos_de_iluminacao`)
  - Texto diferente em R1 e R2.
- **Tomadas de Usos Gerais** (`ele.mdj.instalacoes_eletricas_a_considerar.tomadas_de_usos_gerais`)
  - Texto diferente em R1 e R2.
- **Esquema de Ligação à Terra** (`ele.mdj.instalacoes_eletricas_a_considerar.esquema_de_ligacao_a_terra`)
  - Só em R2.
- **SISTEMA AUTOMÁTICO DE DETEÇÃO DE INCÊNDIO (SADI)** (`ele.mdj.sistema_automatico_de_detecao_de_incendio_sadi`)
  - Bloco só em R2: candidato, a regra de ativação decide.
- **SADI** (`ele.mdj.sistema_automatico_de_detecao_de_incendio_sadi.sadi`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
- **Matriz de Incêndio** (`ele.mdj.sistema_automatico_de_detecao_de_incendio_sadi.matriz_de_incendio`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
- **INSTALAÇÃO FOTOVOLTAICA** (`ele.mdj.instalacao_fotovoltaica`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
- **CARREGAMENTO DE VEÍCULOS ELÉTRICOS** (`ele.mdj.carregamento_de_veiculos_eletricos`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
- **INSTALAÇÃO AUDIOVISUAL - AUDITÓRIO** (`ele.mdj.instalacao_audiovisual_auditorio`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
- **Proteção Contra Contatos Indiretos** (`ele.mdj.protecao_dos_utilizadores.protecao_contra_contatos_indiretos`)
  - Texto diferente em R1 e R2.
- **Circuito de Terras e Elétrodos de Terra** (`ele.mdj.protecao_dos_utilizadores.circuito_de_terras_e_eletrodos_de_terra`)
  - Texto diferente em R1 e R2.

## Biblioteca de blocos · CTE

53 blocos: 15 fixos, 2 paramétricos, 36 adaptativos. Estado: 53 proposto.

| # | Bloco | Modo | Projetos | Regra de ativação | Estado |
|---|---|---|---|---|---|
| 1 | Capa | paramétrico | R1, R2 | `true` | proposto |
| 2 | Índice | fixo | R1, R2 | `true` | proposto |
| 3 | CONDIÇÕES TÉCNICAS GERAIS | fixo | R1, R2 | `true` | proposto |
| 4 | ↳ Introdução | adaptativo | R1, R2 | `true` | proposto |
| 5 | ↳ Características dos Materiais e Equipamentos | fixo | R1, R2 | `true` | proposto |
| 6 | ↳ Ensaios de Receção de Instalação | fixo | R1, R2 | `true` | proposto |
| 7 | ↳ Omissões | fixo | R1, R2 | `true` | proposto |
| 8 | CONDIÇÕES TÉCNICAS ESPECIAIS | fixo | R1, R2 | `true` | proposto |
| 9 | ↳ Entrada de Energia | adaptativo | R1, R2 | `true` | proposto |
| 10 | ↳ Quadros Elétricos | adaptativo | R1, R2 | `true` | proposto |
| 11 | ↳ Canalizações | adaptativo | R1, R2 | `true` | proposto |
| 12 | ↳ Tubos tipo VDLH | fixo | R1, R2 | `true` | proposto |
| 13 | ↳ Tubos tipo ERM | fixo | R1, R2 | `true` | proposto |
| 14 | ↳ Tubos tipo PEAD | fixo | R1, R2 | `true` | proposto |
| 15 | ↳ Cabos e Fios | adaptativo | R1, R2 | `true` | proposto |
| 16 | ↳ Caixas | adaptativo | R1, R2 | `true` | proposto |
| 17 | ↳ Aparelhagem | adaptativo | R1, R2 | `true` | proposto |
| 18 | ↳ Interruptores e Tomadas | adaptativo | R1, R2 | `true` | proposto |
| 19 | ↳ Espelhos | adaptativo | R1 | `true` | proposto |
| 20 | ↳ Detetores de Movimento | adaptativo | R1, R2 | `true` | proposto |
| 21 | ↳ Iluminação Normal | adaptativo | R1, R2 | `true` | proposto |
| 22 | ↳ Videoporteiro | adaptativo | R1 | `any bom.designation ~ "videoporteiro"` | proposto |
| 23 | ↳ Iluminação Segurança | adaptativo | R2 | `sys.iluminacao_seguranca.present or any bom.designation ~ "iluminação de segurança"` | proposto |
| 24 | ↳ Sistema de Controlo KNX | adaptativo | R2 | `any bom.designation ~ "KNX"` | proposto |
| 25 | ↳ Servidor KNX | adaptativo | R2 | `any bom.designation ~ "KNX"` | proposto |
| 26 | ↳ Fonte de Alimentação KNX | adaptativo | R2 | `any bom.designation ~ "KNX"` | proposto |
| 27 | ↳ Gateway DALI/KNX | adaptativo | R2 | `any bom.designation ~ "KNX"` | proposto |
| 28 | ↳ Atuador 8 canais KNX | adaptativo | R2 | `any bom.designation ~ "KNX"` | proposto |
| 29 | ↳ Atuador 4 canais KNX | adaptativo | R2 | `any bom.designation ~ "KNX"` | proposto |
| 30 | ↳ Atuador 10 canais KNX | adaptativo | R2 | `any bom.designation ~ "KNX"` | proposto |
| 31 | ↳ Acoplador de Linha KNX | adaptativo | R2 | `any bom.designation ~ "KNX"` | proposto |
| 32 | ↳ Sensores KNX | adaptativo | R2 | `any bom.designation ~ "KNX"` | proposto |
| 33 | ↳ Sistema fotovoltaico | adaptativo | R2 | `sys.fv.present` | proposto |
| 34 | ↳ Estrutura | adaptativo | R2 | `sys.fv.present` | proposto |
| 35 | ↳ Módulos Fotovoltaicos | adaptativo | R2 | `sys.fv.present` | proposto |
| 36 | ↳ Inversor | adaptativo | R2 | `sys.fv.present` | proposto |
| 37 | ↳ Medidor de energia | adaptativo | R2 | `sys.fv.present` | proposto |
| 38 | ↳ Contador de Energia | adaptativo | R2 | `sys.fv.present` | proposto |
| 39 | ↳ Sistema de Alarme e Deteção de Incêndio (SADI) | adaptativo | R2 | `any bom.chapter ~ "deteção de incêndio"` | proposto |
| 40 | ↳ Carregamento de Veículos Elétricos | adaptativo | R2 | `sys.ve.present` | proposto |
| 41 | ↳ Sistema Audiovisual | adaptativo | R2 | `any bom.chapter ~ "audiovisual"` | proposto |
| 42 | ↳ Sistema de Vídeo e Projeção | adaptativo | R2 | `any bom.chapter ~ "audiovisual"` | proposto |
| 43 | ↳ Sistema de Conferência e Microfonia | adaptativo | R2 | `any bom.chapter ~ "audiovisual"` | proposto |
| 44 | ↳ Sistema de Reforço Sonoro (PA) | adaptativo | R2 | `any bom.chapter ~ "audiovisual"` | proposto |
| 45 | ↳ Iluminação de Palco | adaptativo | R2 | `any bom.chapter ~ "audiovisual"` | proposto |
| 46 | ↳ Sistema de Controlo e Automação | adaptativo | R2 | `any bom.chapter ~ "audiovisual"` | proposto |
| 47 | ↳ Rede de Terras | fixo | R1, R2 | `true` | proposto |
| 48 | ↳ Elétrodos de Terra | fixo | R1, R2 | `true` | proposto |
| 49 | ↳ Caixa de Visita com Ligador Amovível | fixo | R1, R2 | `true` | proposto |
| 50 | ↳ Condutores de Proteção | fixo | R1, R2 | `true` | proposto |
| 51 | ↳ Ligações Equipotenciais | fixo | R1, R2 | `true` | proposto |
| 52 | DÚVIDAS E CASOS OMISSOS | fixo | R1, R2 | `true` | proposto |
| 53 | Local, data e técnico | paramétrico | R1, R2 | `true` | proposto |

#### O que pedir atenção no CTE

- **Índice** (`ele.cte.indice`)
  - Índice: o Word atualiza-o ao abrir.
- **Introdução** (`ele.cte.condicoes_tecnicas_gerais.introducao`)
  - Texto diferente em R1 e R2. Tem valores do projeto: fica adaptativo.
- **Ensaios de Receção de Instalação** (`ele.cte.condicoes_tecnicas_gerais.ensaios_de_rececao_de_instalacao`)
  - Texto diferente em R2: fica o de R1 (condições gerais, a confirmar).
- **Entrada de Energia** (`ele.cte.condicoes_tecnicas_especiais.entrada_de_energia`)
  - Texto diferente em R1 e R2.
  - Só em R1.
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 1).
- **Quadros Elétricos** (`ele.cte.condicoes_tecnicas_especiais.quadros_eletricos`)
  - Texto diferente em R1 e R2.
  - Só em R1.
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 1).
- **Canalizações** (`ele.cte.condicoes_tecnicas_especiais.canalizacoes`)
  - Texto diferente em R1 e R2.
- **Tubos tipo VDLH** (`ele.cte.condicoes_tecnicas_especiais.tubos_tipo_vdlh`)
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 1).
- **Tubos tipo ERM** (`ele.cte.condicoes_tecnicas_especiais.tubos_tipo_erm`)
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 1).
- **Tubos tipo PEAD** (`ele.cte.condicoes_tecnicas_especiais.tubos_tipo_pead`)
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 1).
- **Cabos e Fios** (`ele.cte.condicoes_tecnicas_especiais.cabos_e_fios`)
  - Texto diferente em R1 e R2.
  - Só em R1.
- **Caixas** (`ele.cte.condicoes_tecnicas_especiais.caixas`)
  - Texto diferente em R1 e R2.
  - Só em R1.
  - Só em R2.
  - 4 lugar(es) de equipamento de referência (ou equivalente: 4).
- **Aparelhagem** (`ele.cte.condicoes_tecnicas_especiais.aparelhagem`)
  - Texto diferente em R1 e R2.
- **Interruptores e Tomadas** (`ele.cte.condicoes_tecnicas_especiais.interruptores_e_tomadas`)
  - Texto diferente em R1 e R2.
  - 5 lugar(es) de equipamento de referência (marca/modelo: 3, ou equivalente: 4).
- **Espelhos** (`ele.cte.condicoes_tecnicas_especiais.espelhos`)
  - Bloco só em R1: candidato, a regra de ativação decide.
  - Só em R1.
  - 4 lugar(es) de equipamento de referência (marca/modelo: 1, ou equivalente: 3).
- **Detetores de Movimento** (`ele.cte.condicoes_tecnicas_especiais.detetores_de_movimento`)
  - Texto diferente em R1 e R2.
  - Só em R2.
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1).
- **Iluminação Normal** (`ele.cte.condicoes_tecnicas_especiais.iluminacao_normal`)
  - Texto diferente em R1 e R2.
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 1).
- **Videoporteiro** (`ele.cte.condicoes_tecnicas_especiais.videoporteiro`)
  - Bloco só em R1: candidato, a regra de ativação decide.
  - Só em R1.
  - 2 lugar(es) de equipamento de referência (marca/modelo: 2).
- **Iluminação Segurança** (`ele.cte.condicoes_tecnicas_especiais.iluminacao_seguranca`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 1).
- **Sistema de Controlo KNX** (`ele.cte.condicoes_tecnicas_especiais.sistema_de_controlo_knx`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
- **Servidor KNX** (`ele.cte.condicoes_tecnicas_especiais.servidor_knx`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
  - 2 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 2).
- **Fonte de Alimentação KNX** (`ele.cte.condicoes_tecnicas_especiais.fonte_de_alimentacao_knx`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 1).
- **Gateway DALI/KNX** (`ele.cte.condicoes_tecnicas_especiais.gateway_dali_knx`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 1).
- **Atuador 8 canais KNX** (`ele.cte.condicoes_tecnicas_especiais.atuador_8_canais_knx`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 1).
- **Atuador 4 canais KNX** (`ele.cte.condicoes_tecnicas_especiais.atuador_4_canais_knx`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 1).
- **Atuador 10 canais KNX** (`ele.cte.condicoes_tecnicas_especiais.atuador_10_canais_knx`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 1).
- **Acoplador de Linha KNX** (`ele.cte.condicoes_tecnicas_especiais.acoplador_de_linha_knx`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 1).
- **Sensores KNX** (`ele.cte.condicoes_tecnicas_especiais.sensores_knx`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
  - 3 lugar(es) de equipamento de referência (ou equivalente: 3).
- **Sistema fotovoltaico** (`ele.cte.condicoes_tecnicas_especiais.sistema_fotovoltaico`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
- **Estrutura** (`ele.cte.condicoes_tecnicas_especiais.estrutura`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1).
- **Módulos Fotovoltaicos** (`ele.cte.condicoes_tecnicas_especiais.modulos_fotovoltaicos`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 1).
- **Inversor** (`ele.cte.condicoes_tecnicas_especiais.inversor`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 1).
- **Medidor de energia** (`ele.cte.condicoes_tecnicas_especiais.medidor_de_energia`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
- **Contador de Energia** (`ele.cte.condicoes_tecnicas_especiais.contador_de_energia`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 1).
- **Sistema de Alarme e Deteção de Incêndio (SADI)** (`ele.cte.condicoes_tecnicas_especiais.sistema_de_alarme_e_detecao_de_incendio_sadi`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
  - 3 lugar(es) de equipamento de referência (marca/modelo: 3, ou equivalente: 2).
- **Carregamento de Veículos Elétricos** (`ele.cte.condicoes_tecnicas_especiais.carregamento_de_veiculos_eletricos`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1).
- **Sistema Audiovisual** (`ele.cte.condicoes_tecnicas_especiais.sistema_audiovisual`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
- **Sistema de Vídeo e Projeção** (`ele.cte.condicoes_tecnicas_especiais.sistema_de_video_e_projecao`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1).
- **Sistema de Conferência e Microfonia** (`ele.cte.condicoes_tecnicas_especiais.sistema_de_conferencia_e_microfonia`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
  - 2 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 1).
- **Sistema de Reforço Sonoro (PA)** (`ele.cte.condicoes_tecnicas_especiais.sistema_de_reforco_sonoro_pa`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
- **Iluminação de Palco** (`ele.cte.condicoes_tecnicas_especiais.iluminacao_de_palco`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
  - 3 lugar(es) de equipamento de referência (ou equivalente: 3).
- **Sistema de Controlo e Automação** (`ele.cte.condicoes_tecnicas_especiais.sistema_de_controlo_e_automacao`)
  - Bloco só em R2: candidato, a regra de ativação decide.
  - Só em R2.
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1).
- **Elétrodos de Terra** (`ele.cte.condicoes_tecnicas_especiais.eletrodos_de_terra`)
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 1).
- **Caixa de Visita com Ligador Amovível** (`ele.cte.condicoes_tecnicas_especiais.caixa_de_visita_com_ligador_amovivel`)
  - 1 lugar(es) de equipamento de referência (ou equivalente: 1, marca/modelo: 1).

## Regras de ativação: diferenças esperadas

Sobre R1 e R2, as regras propostas reproduzem os blocos presentes nas MDJ e nos CTE, exceto aqui (os testes verificam que são as únicas):

| Bloco | Projeto | Porque a regra e o documento não coincidem |
|---|---|---|
| `ele.mdj.canalizacoes.canalizacoes_enterradas` | R2 | C12: o troço Portinhola → Q.E.G. de R2 é enterrado (ENT) e a MDJ de R2 não tem canalizações enterradas. |
| `ele.mdj.instalacao_de_alimentacao_distribuicao_e_medida_de_energia.distribuicao_de_energia` | R2 | O esqueleto 8.3 põe a distribuição sempre; a MDJ de R2 não tem esta secção. |
| `ele.mdj.instalacoes_eletricas_a_considerar.iluminacao_de_seguranca` | R1 | O MQT de R1 tem iluminação de segurança e a MDJ de R1 não tem o bloco. |
| `ele.mdj.instalacoes_eletricas_a_considerar.iluminacao_de_seguranca` | R2 | A LPU de R2 tem iluminação de segurança (e a MDJ lista-a nas instalações a considerar), mas não tem o bloco. |
| `ele.cte.condicoes_tecnicas_especiais.espelhos` | R2 | O esqueleto 8.3 põe os espelhos sempre (com a aparelhagem); o CTE de R2 não tem esta secção, embora a LPU tenha espelhos. |
| `ele.cte.condicoes_tecnicas_especiais.iluminacao_seguranca` | R1 | O MQT de R1 tem iluminação de segurança e o CTE de R1 não tem o bloco. |

## Dicionário de cabos

| Designação | Tipo | Condutor | Onde aparece | Estado |
|---|---|---|---|---|
| `FXZ1` | cabo | — | R2 · CTE (2), R2 · MDJ (1) | proposto |
| `H07V-K` | fio | flexível | R1 · MDJ (1), R1 · MQT (8) | proposto |
| `H07V-R` | fio | rígido | R2 · LPU (1) | proposto |
| `H07V-U` | fio | rígido | R1 · CTE (2), R1 · Tabela (5) | proposto |
| `RV-K` | cabo | flexível | R1 · CTE (1), R1 · MDJ (2), R1 · MQT (2), R1 · Tabela (1), R2 · CTE (1), R2 · LPU (1), R2 · Tabela (6) | proposto |
| `RZ1-K (AS)` | cabo | flexível | R2 · Tabela (13) | proposto |
| `SZ1(frt,zh)` | cabo | — | R2 · LPU (1) | proposto |
| `XAV` | cabo | — | R2 · LPU (1), R2 · Tabela (1) | proposto |
| `XV` | cabo | — | R1 · CTE (1), R2 · CTE (1) | proposto |
| `XV-R` | cabo | rígido | R1 · MQT (2) | proposto |
| `XZ1(frs,zh)` | cabo | — | R2 · LPU (4) | proposto |
| `XZ1(frt,zh)` | cabo | — | R2 · LPU (14) | proposto |

Equivalências propostas (nunca entre um fio rígido e um flexível):

- **`RV-K` ≈ `XZ1(frs,zh)`** (proposto). No mesmo projeto, a mesma secção e o mesmo número de condutores aparecem com as duas designações em fontes diferentes (ex.: Tabela de Cálculo e MQT/LPU).
  - R2, secção 3G10: «RV-K 3G10mm2» (Tabela, Folha1!linha 27) e «XZ1(frs,zh) 3G10mm²» (LPU, LPU!linha 34)
  - R2, secção 3G10: «RV-K 3G10mm2» (Tabela, Folha1!linha 28) e «XZ1(frs,zh) 3G10mm²» (LPU, LPU!linha 34)
  - R2, secção 3G10: «RV-K 3G10mm2» (Tabela, Folha1!linha 29) e «XZ1(frs,zh) 3G10mm²» (LPU, LPU!linha 34)
- **`RZ1-K (AS)` ≈ `XZ1(frt,zh)`** (proposto). No mesmo projeto, a mesma secção e o mesmo número de condutores aparecem com as duas designações em fontes diferentes (ex.: Tabela de Cálculo e MQT/LPU).
  - R2, secção 5G10: «RZ1-K (AS) 5G10mm2» (Tabela, Folha1!linha 14) e «XZ1(frt,zh) 5G10mm²» (LPU, LPU!linha 30)
  - R2, secção 5G10: «RZ1-K (AS) 5G10mm2» (Tabela, Folha1!linha 14) e «XZ1(frt,zh) 5G10mm²» (LPU, LPU!linha 218)
  - R2, secção 5G10: «RZ1-K (AS) 5G10mm2» (Tabela, Folha1!linha 16) e «XZ1(frt,zh) 5G10mm²» (LPU, LPU!linha 30)
- **`RZ1-K (AS)` ≈ `XZ1(frs,zh)`** (proposto). No mesmo projeto, a mesma secção e o mesmo número de condutores aparecem com as duas designações em fontes diferentes (ex.: Tabela de Cálculo e MQT/LPU).
  - R2, secção 5G4: «RZ1-K (AS) 5G4mm2» (Tabela, Folha1!linha 15) e «XZ1(frs,zh) 5G4mm²» (LPU, LPU!linha 32)
  - R2, secção 5G4: «RZ1-K (AS) 5G4mm2» (Tabela, Folha1!linha 18) e «XZ1(frs,zh) 5G4mm²» (LPU, LPU!linha 32)
  - R2, secção 5G4: «RZ1-K (AS) 5G4mm2» (Tabela, Folha1!linha 21) e «XZ1(frs,zh) 5G4mm²» (LPU, LPU!linha 32)

## Léxico de tipologias (regra TIP-01)

- **biblioteca** (proposto). Evidência: R2 · Ficha eletrotécnica: «Outros»; R2 · Ficha eletrotécnica: «Estabelecimentos recebendo público»; R2 · Ficha eletrotécnica: «Escritório»; R2 · MDJ (capa): «OBRA: Reabilitação da Biblioteca Municipal de Cantanhede»
  - «apartamento» (proposto): não aparece nos documentos de referência
  - «fração» (proposto): não aparece nos documentos de referência
  - «habitação unifamiliar» (proposto): não aparece nos documentos de referência
  - «moradia unifamiliar» (proposto): não aparece nos documentos de referência
- **moradia unifamiliar** (proposto). Evidência: R1 · Ficha eletrotécnica: «Unifamiliar»; R1 · Ficha eletrotécnica: «Locais de habitação»; R1 · Ficha eletrotécnica: «Habitação»; R1 · MDJ (capa): «OBRA: MORADIA UNIFAMILIAR - MBERAL»
  - «apartamento» (proposto): encontrado 1 vez(es), ex.: R1 · CTE · parágrafo 224: «…gica e estética, um ecrã tátil na entrada de cada apartamento com características de design elegante e minimali…»
  - «condomínio» (proposto): não aparece nos documentos de referência
  - «condóminos» (proposto): não aparece nos documentos de referência
  - «fração» (proposto): não aparece nos documentos de referência
  - «habitação coletiva» (proposto): não aparece nos documentos de referência
  - «partes comuns» (proposto): não aparece nos documentos de referência

## Corpus regulamentar (Anexo D)

Só referências: título, âmbito e onde R1/R2 as citam. Tudo por confirmar e não citável. A pesquisa no texto integral (RegulationChunk) fica para mais tarde.

| Documento | Tipo | Âmbito | Citado em R1/R2 | Estado | Citável |
|---|---|---|---|---|---|
| Decreto-Lei n.º 96/2017 | diploma | Instalações elétricas de serviço particular: termo de responsabilidade e identificação do projeto. | 2 vez(es): R1 · Formulário | proposto | não |
| Despacho n.º 1/2018 da DGEG | diploma | Classificação das instalações usada na ficha eletrotécnica. | **não citado** | proposto | não |
| Portaria n.º 701-H/2008 | diploma | Conteúdo obrigatório dos projetos de obras públicas. | **não citado** | proposto | não |
| RTIEBT: Portaria n.º 949-A/2006, na redação atual | diploma | Regras Técnicas das Instalações Elétricas de Baixa Tensão. | 26 vez(es): R1 · CTE, R1 · MDJ, R2 · CTE, R2 · MDJ | proposto | não |
| Especificações da E-REDES (ex.: DMA-C65-210/N) | especificacao | Especificações do operador da rede de distribuição, por exemplo elétrodos de terra. | 2 vez(es): R1 · CTE, R2 · CTE | proposto | não |
| Guia Técnico das classes de reação ao fogo dos cabos elétricos (RPC) | guia | Classes de reação ao fogo dos cabos (Regulamento dos Produtos de Construção). | 3 vez(es): R2 · MDJ | proposto | não |
| Guia Técnico das Instalações Elétricas para carregamento de VE | guia | Instalações de carregamento de veículos elétricos. | 2 vez(es): R1 · MDJ, R2 · MDJ | proposto | não |
| EN 12464-1 | norma | Iluminação de locais de trabalho interiores. (só título e âmbito: direitos de autor) | 1 vez(es): R2 · MDJ | proposto | não |
| EN 50086-2-4 | norma | Sistemas de tubos enterrados. (só título e âmbito: direitos de autor) | 2 vez(es): R1 · CTE, R2 · CTE | proposto | não |
| EN 60898 | norma | Disjuntores para instalações domésticas e análogas. (só título e âmbito: direitos de autor) | 4 vez(es): R1 · CTE, R1 · MDJ, R2 · CTE, R2 · MDJ | proposto | não |
| HD 602 / HD 606 | norma | Comportamento dos cabos em caso de incêndio. (só título e âmbito: direitos de autor) | 1 vez(es): R2 · MDJ | proposto | não |
| NP EN 50102 | norma | Graus de proteção contra impactos mecânicos (códigos IK). (só título e âmbito: direitos de autor) | 2 vez(es): R1 · MDJ, R2 · MDJ | proposto | não |
| NP EN 60529 | norma | Graus de proteção dos invólucros (códigos IP). (só título e âmbito: direitos de autor) | 2 vez(es): R1 · MDJ, R2 · MDJ | proposto | não |
| NP EN 61386 | norma | Sistemas de tubos para instalações elétricas. (só título e âmbito: direitos de autor) | 4 vez(es): R1 · CTE, R2 · CTE | proposto | não |
