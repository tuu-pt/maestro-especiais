# Fase 8 · Guia do piloto

O piloto são **três projetos reais de eletricidade feitos no Maestro Especiais**. Para cada um, compara-se o tempo
com o processo manual (SPEC 14).

A meta (SPEC 1) tem duas partes:
- reduzir pelo menos **40 %** do tempo da MDJ, do CTE e dos formulários;
- **zero incoerências** de identificação, potência e cabos nas peças aprovadas.

A aplicação mede sozinha; o técnico só escreve a estimativa do processo manual e regista os problemas que encontrar.

## Antes de começar

1. **Contas.** Cada pessoa tem a sua conta (`make create-user EMAIL=… NAME="…" ROLES=…`) e entra em `/entrar`.
   - O tempo é guardado por pessoa, por isso não se partilham contas.
2. **Perfil do técnico real.** Em Definições → perfil do técnico, preencher nome, título, n.º OET/DGEG, contactos,
   morada e local de assinatura.
   - Os valores de teste (zeros e «teste») saem nas capas e nos formulários se ficarem lá.
3. **Blocos aprovados.** Em Conhecimento → Biblioteca de blocos: sem eles só sai o rascunho.
   - Em 9 out 2026: os 95 aprovados pelo admin, com a D7 provisória.
4. **LLM.** Em Definições → Modelos de linguagem, confirmar o fornecedor principal e que há pelo menos um pronto.
5. **A estimativa, antes de começar o projeto.**
   - No ecrã **Piloto** do projeto, o técnico escreve quanto tempo levaria à mão cada um dos 8 passos, em minutos
     («de… a…»), as voltas de correção habituais e os erros mais frequentes.
   - Escrita antes, não é influenciada pelo tempo na aplicação.

## Os 8 passos medidos

| Passo | Onde conta |
|---|---|
| Juntar e conferir os dados de partida | carregamento dos ficheiros |
| Ficha eletrotécnica e ficha-base | Ficha do projeto |
| Escrever a MDJ / Escrever o CTE | Editor, com a MDJ ou o CTE aberto |
| Identificação, termo e ficha eletrotécnica | secção «Formulários» do Editor |
| Verificar a coerência entre peças | Validação e Equipamentos |
| Corrigir o que a revisão aponta | Ficha, Editor e Formulários **depois do primeiro envio para revisão** |
| Montar o conjunto final | Revisão (aprovação e exportação) |

**Como o tempo é contado:**
- Conta o tempo ativo: o separador visível e alguma interação (rato, teclado, scroll) nos últimos 2 minutos.
- Uma pausa mais longa não conta.
- O trabalho fora da aplicação (telefonemas, deslocações, CAD) não conta. Se for relevante, registar como problema,
  com o tempo aproximado.

## Durante o projeto

1. Criar o projeto no Painel e carregar os ficheiros: ficha eletrotécnica, Tabela de Cálculo, 09-Folhas, MQT/LPU e
   PDF das peças desenhadas.
2. Resolver os conflitos e confirmar a ficha-base (técnico).
3. Montar e redigir a MDJ e o CTE no Editor. Rever cada secção e descarregar os formulários.
4. Validar e corrigir. Enviar para revisão.
5. O técnico aprova as peças e exporta o conjunto.

**Sempre que algo estiver errado ou faltar, usar «Registar problema»**, no topo de qualquer ecrã. Por exemplo:
- um bloco a corrigir;
- um alerta que não faz sentido;
- um valor mal lido;
- um passo lento.

Fica ligado ao projeto e ao ecrã. **Não escrever nomes, moradas nem contactos.** O relatório omite uma nota que tenha
um dado pessoal do projeto e mascara emails, NIF, telefones e moradas.

## No fim

- O ecrã **Piloto**, sem projeto ativo, mostra todos os projetos. Com um projeto ativo, mostra o detalhe:
  - tempo por passo contra a estimativa;
  - redução;
  - incoerências em cada aprovação;
  - problemas.
- Em cada aprovação contam-se as incoerências de identificação (COE-04), potência (COE-05) e cabos (COE-06):
  - as **encontradas** durante o projeto;
  - as que ainda estavam **abertas** ou **ignoradas** quando a peça foi aprovada.

  A meta exige zero abertas e zero ignoradas.
- `make pilot-report` escreve `docs/fase8-piloto.md` para a equipa. Só leva o código do projeto, a tipologia, os
  números e os problemas (com os dados pessoais omitidos).
  - **Confirmar o conteúdo antes de o partilhar ou fazer commit.**
- Os problemas resolvidos marcam-se no ecrã Piloto (admin ou curador).

## O que o agente não faz

O Claude Code não lê os projetos reais nem corre o relatório sobre eles. Também não aprova peças nem blocos.
