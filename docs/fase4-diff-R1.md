# Fase 4 · Diferenças entre a montagem e o original de R1

Gerado por `make diff-report` (`app/assembly/diff_report.py`) a partir da stack de
desenvolvimento: R1 carregado de `data/fixtures`, ficha-base confirmada, MDJ e CTE
montados com a biblioteca proposta e os adaptativos redigidos pelo agente. Cada entrada
de cada bloco é comparada com os elementos do original de onde veio.
Não mostra valores pessoais.

| Documento | Secções | Entradas | Iguais | Adaptativo | Valor | Estrutura | Defeito |
|---|---|---|---|---|---|---|---|
| MDJ | 42 | 268 | 225 | 17 | 12 | 9 | **0** |
| CTE | 53 | 242 | 172 | 12 | 12 | 34 | **0** |

Classes: **texto adaptativo** (redigido pelo agente: diferente por natureza; a semelhança
é alta porque o arquivo inclui o próprio R1, num projeto novo não), **valor** (a
ficha-base ou o perfil do técnico dão outro valor, ou falta o valor), **estrutura**
(índice atualizado pelo Word e blocos de outro projeto, desativados pelas regras ou sem
texto) e
**defeito** (texto literal diferente do original, sem explicação). Os alertas do texto do
agente (NUM-01: números fora de marcador, em geral distâncias e valores regulamentares
copiados das fontes) ficam na versão para o técnico confirmar; a regra não é relaxada.

## MDJ

Alertas no texto do agente: NUM-01: 3.

**Incoerências conhecidas (Anexo C)**

| # | O quê | Na montagem |
|---|---|---|
| C1 | MDJ com fios H07V-K; CTE e Tabela com H07V-U | Canalizações Embebidas ou Ocultas: o agente repete-a (deteção na Fase 5) |

### Texto adaptativo (17)

| Secção | Entrada | Tipo | Detalhe |
|---|---|---|---|
| INTRODUÇÃO | 2 | texto do agente | entradas 2: 2 parágrafo(s), proposta por aceitar; semelhança com o original 92% |
| CLASSIFICAÇÃO QUANTO À UTILIZAÇÃO DO LOCAL | 2 | texto do agente | entradas 2: 1 parágrafo(s), proposta por aceitar; semelhança com o original 59% |
| Alimentação de Energia | 1 | texto do agente | entradas 1: 1 parágrafo(s), proposta por aceitar; semelhança com o original 100% |
| Contagem | 1 | texto do agente | entradas 1: 1 parágrafo(s), proposta por aceitar; semelhança com o original 95% |
| Distribuição de Energia | 1 | texto do agente | entradas 1, 2, 3, 4: 4 parágrafo(s), proposta por aceitar; semelhança com o original 86% |
| QUADRO ELÉTRICO | 2 | texto do agente | entradas 2: 1 parágrafo(s), proposta por aceitar; semelhança com o original 94% |
| CANALIZAÇÕES | 2 | texto do agente | entradas 2: 1 parágrafo(s), proposta por aceitar; semelhança com o original 100% |
| Canalizações Embebidas ou Ocultas | 1 | texto do agente | entradas 1: 1 parágrafo(s), proposta por aceitar; semelhança com o original 55% |
| Canalizações Enterradas | 1 | texto do agente | entradas 1, 2, 3, 4, 5, 6, 7, 8: 2 parágrafo(s), proposta por aceitar; semelhança com o original 18% |
| CAIXAS | 7 | texto do agente | entradas 7: 1 parágrafo(s), proposta por aceitar; semelhança com o original 9% |
| INSTALAÇÕES ELÉTRICAS A CONSIDERAR | 6 | texto do agente | entradas 6, 8: 1 parágrafo(s), proposta por aceitar; semelhança com o original 42% |
| Iluminação Normal | 2 | texto do agente | entradas 2, 5, 6, 7: 1 parágrafo(s), proposta por aceitar; semelhança com o original 100% |
| Comandos de Iluminação | 1 | texto do agente | entradas 1: 1 parágrafo(s), proposta por aceitar; semelhança com o original 100% |
| Tomadas de Usos Gerais | 1 | texto do agente | entradas 1: 2 parágrafo(s), proposta por aceitar; semelhança com o original 100% |
| Esquema de Ligação à Terra | 7 | parágrafo de outro projeto | entradas 7, 8, 9, 10: 3 parágrafo(s) do agente |
| Proteção Contra Contatos Indiretos | 1 | texto do agente | entradas 1: 2 parágrafo(s), proposta por aceitar; semelhança com o original 92% |
| Circuito de Terras e Elétrodos de Terra | 1 | texto do agente | entradas 1: 2 parágrafo(s), proposta por aceitar; semelhança com o original 94% |

### Valor da ficha-base ou do perfil (12)

| Secção | Entrada | Tipo | Detalhe |
|---|---|---|---|
| Capa | 2 | ficha-base ≠ original | Requerente: o original usa a forma curta do nome; a ficha-base tem a designação completa do requerente |
| Capa | 4 | ficha-base ≠ original | Rua: a capa do original tem outra morada que a ficha eletrotécnica (com n.º de porta; pseudónimos diferentes, logo textos reais diferentes): a ficha-base é a fonte de verdade [A CONFIRMAR pela equipa] |
| Capa | 5 | falta na ficha-base | Código postal: sem valor na ficha-base confirmada |
| Capa | 5 | maiúsculas | Concelho: mesmo valor; o original está em maiúsculas |
| Capa | 8 | falta na ficha-base | Designação da obra: sem valor na ficha-base confirmada |
| Local, data e técnico | 0 | perfil do técnico | Local (assinatura): do perfil de quem confirmou a ficha |
| Local, data e técnico | 0 | data pelo técnico (P8) | a data fica vazia: o técnico data e assina |
| Local, data e técnico | 5 | perfil do técnico | Nome do técnico: do perfil de quem confirmou a ficha |
| Local, data e técnico | 5 | perfil do técnico | Título profissional do técnico: do perfil de quem confirmou a ficha |
| Local, data e técnico | 6 | perfil do técnico | Cartão de cidadão do técnico: do perfil de quem confirmou a ficha |
| Local, data e técnico | 7 | perfil do técnico | N.º de membro OET do técnico: do perfil de quem confirmou a ficha (C3: o n.º OET passa a vir só do perfil) |
| Local, data e técnico | 8 | perfil do técnico | Código de verificação das competências: do perfil de quem confirmou a ficha |

### Estrutura (índice e blocos de outro projeto) (9)

| Secção | Entrada | Tipo | Detalhe |
|---|---|---|---|
| Índice | — | índice | campo do Word: é atualizado ao abrir o rascunho (updateFields) |
| REGULAMENTO DOS PRODUTOS DE CONSTRUÇÃO (RPC) | — | bloco de outro projeto | inativa pela regra |
| Iluminação de Segurança | — | bloco de outro projeto | ativa, sem texto de R1 |
| SISTEMA AUTOMÁTICO DE DETEÇÃO DE INCÊNDIO (SADI) | — | bloco de outro projeto | inativa pela regra |
| SADI | — | bloco de outro projeto | inativa pela regra |
| Matriz de Incêndio | — | bloco de outro projeto | inativa pela regra |
| INSTALAÇÃO FOTOVOLTAICA | — | bloco de outro projeto | inativa pela regra |
| CARREGAMENTO DE VEÍCULOS ELÉTRICOS | — | bloco de outro projeto | inativa pela regra |
| INSTALAÇÃO AUDIOVISUAL - AUDITÓRIO | — | bloco de outro projeto | inativa pela regra |


## CTE

Alertas no texto do agente: NUM-01: 45.

**Incoerências conhecidas (Anexo C)**

| # | O quê | Na montagem |
|---|---|---|
| C2 | CTE: «apartamento» numa moradia unifamiliar | Videoporteiro: o agente não a repete no texto redigido |

### Texto adaptativo (12)

| Secção | Entrada | Tipo | Detalhe |
|---|---|---|---|
| Introdução | 1 | texto do agente | entradas 1: 1 parágrafo(s), proposta por aceitar; semelhança com o original 76% |
| Entrada de Energia | 1 | texto do agente | entradas 1: 3 parágrafo(s), proposta por aceitar; semelhança com o original 63% |
| Quadros Elétricos | 1 | texto do agente | entradas 1, 5: 3 parágrafo(s), proposta por aceitar; semelhança com o original 52% |
| Canalizações | 1 | texto do agente | entradas 1: 1 parágrafo(s), proposta por aceitar; semelhança com o original 72% |
| Cabos e Fios | 1 | texto do agente | entradas 1: 1 parágrafo(s), proposta por aceitar; semelhança com o original 85% |
| Caixas | 7 | texto do agente | entradas 7: 9 parágrafo(s), proposta por aceitar; semelhança com o original 100% |
| Aparelhagem | 1 | texto do agente | entradas 1: 3 parágrafo(s), proposta por aceitar; semelhança com o original 84% |
| Interruptores e Tomadas | 2 | texto do agente | entradas 2, 5, 8, 11: 4 parágrafo(s), proposta por aceitar; semelhança com o original 87% |
| Espelhos | 1 | texto do agente | entradas 1, 2, 5, 8: 1 parágrafo(s), proposta por aceitar; semelhança com o original 100% |
| Detetores de Movimento | 1 | texto do agente | entradas 1: 2 parágrafo(s), proposta por aceitar; semelhança com o original 38% |
| Iluminação Normal | 2 | texto do agente | entradas 2, 6: 2 parágrafo(s), proposta por aceitar; semelhança com o original 43% |
| Videoporteiro | 1 | texto do agente | entradas 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34: 6 parágrafo(s), proposta por aceitar; semelhança com o original 54% |

### Valor da ficha-base ou do perfil (12)

| Secção | Entrada | Tipo | Detalhe |
|---|---|---|---|
| Capa | 2 | ficha-base ≠ original | Requerente: o original usa a forma curta do nome; a ficha-base tem a designação completa do requerente |
| Capa | 4 | ficha-base ≠ original | Rua: a capa do original tem outra morada que a ficha eletrotécnica (com n.º de porta; pseudónimos diferentes, logo textos reais diferentes): a ficha-base é a fonte de verdade [A CONFIRMAR pela equipa] |
| Capa | 5 | falta na ficha-base | Código postal: sem valor na ficha-base confirmada |
| Capa | 5 | maiúsculas | Concelho: mesmo valor; o original está em maiúsculas |
| Capa | 8 | falta na ficha-base | Designação da obra: sem valor na ficha-base confirmada |
| Local, data e técnico | 0 | perfil do técnico | Local (assinatura): do perfil de quem confirmou a ficha |
| Local, data e técnico | 0 | data pelo técnico (P8) | a data fica vazia: o técnico data e assina |
| Local, data e técnico | 4 | perfil do técnico | Nome do técnico: do perfil de quem confirmou a ficha |
| Local, data e técnico | 4 | perfil do técnico | Título profissional do técnico: do perfil de quem confirmou a ficha |
| Local, data e técnico | 5 | perfil do técnico | Cartão de cidadão do técnico: do perfil de quem confirmou a ficha |
| Local, data e técnico | 6 | perfil do técnico | N.º de membro OET do técnico: do perfil de quem confirmou a ficha (C3: o n.º OET passa a vir só do perfil) |
| Local, data e técnico | 7 | perfil do técnico | Código de verificação das competências: do perfil de quem confirmou a ficha |

### Estrutura (índice e blocos de outro projeto) (34)

| Secção | Entrada | Tipo | Detalhe |
|---|---|---|---|
| Índice | — | índice | campo do Word: é atualizado ao abrir o rascunho (updateFields) |
| Entrada de Energia | 2 | imagem de um só projeto | só em R1: não incluída (equipamento, Fase 7) |
| Quadros Elétricos | 9 | imagem de um só projeto | só em R1: não incluída (equipamento, Fase 7) |
| Cabos e Fios | 2 | imagem de um só projeto | só em R1: não incluída (equipamento, Fase 7) |
| Caixas | 14 | imagem de um só projeto | só em R1: não incluída (equipamento, Fase 7) |
| Caixas | 17 | imagem de um só projeto | só em R2: não incluída (equipamento, Fase 7) |
| Espelhos | 3 | imagem de um só projeto | só em R1: não incluída (equipamento, Fase 7) |
| Espelhos | 6 | imagem de um só projeto | só em R1: não incluída (equipamento, Fase 7) |
| Espelhos | 9 | imagem de um só projeto | só em R1: não incluída (equipamento, Fase 7) |
| Detetores de Movimento | 4 | imagem de um só projeto | só em R2: não incluída (equipamento, Fase 7) |
| Iluminação Segurança | — | bloco de outro projeto | ativa, com texto de outro projeto |
| Sistema de Controlo KNX | — | bloco de outro projeto | inativa pela regra |
| Servidor KNX | — | bloco de outro projeto | inativa pela regra |
| Fonte de Alimentação KNX | — | bloco de outro projeto | inativa pela regra |
| Gateway DALI/KNX | — | bloco de outro projeto | inativa pela regra |
| Atuador 8 canais KNX | — | bloco de outro projeto | inativa pela regra |
| Atuador 4 canais KNX | — | bloco de outro projeto | inativa pela regra |
| Atuador 10 canais KNX | — | bloco de outro projeto | inativa pela regra |
| Acoplador de Linha KNX | — | bloco de outro projeto | inativa pela regra |
| Sensores KNX | — | bloco de outro projeto | inativa pela regra |
| Sistema fotovoltaico | — | bloco de outro projeto | inativa pela regra |
| Estrutura | — | bloco de outro projeto | inativa pela regra |
| Módulos Fotovoltaicos | — | bloco de outro projeto | inativa pela regra |
| Inversor | — | bloco de outro projeto | inativa pela regra |
| Medidor de energia | — | bloco de outro projeto | inativa pela regra |
| Contador de Energia | — | bloco de outro projeto | inativa pela regra |
| Sistema de Alarme e Deteção de Incêndio (SADI) | — | bloco de outro projeto | inativa pela regra |
| Carregamento de Veículos Elétricos | — | bloco de outro projeto | inativa pela regra |
| Sistema Audiovisual | — | bloco de outro projeto | inativa pela regra |
| Sistema de Vídeo e Projeção | — | bloco de outro projeto | inativa pela regra |
| Sistema de Conferência e Microfonia | — | bloco de outro projeto | inativa pela regra |
| Sistema de Reforço Sonoro (PA) | — | bloco de outro projeto | inativa pela regra |
| Iluminação de Palco | — | bloco de outro projeto | inativa pela regra |
| Sistema de Controlo e Automação | — | bloco de outro projeto | inativa pela regra |
