# Fase 6 · Verificação manual no Word e no Excel (Windows)

O que as verificações automáticas não conseguem ver (`app/export/checks.py`: pacote, relações, IDs, estilos, imagens,
fórmulas, tabelas, conversão pelo LibreOffice, partes do .xlsm iguais ao modelo, releitura da ficha). Faz-se uma vez com
o conjunto de R1 e de novo quando mudar o modelo ou a montagem.

## Como obter os ficheiros

1. `make up`, `make seed-library` e `RUN_EXPORT_JOURNEY=1 npm run e2e` (em `frontend/`), ou o mesmo à mão no ecrã H.
2. No ecrã H do projeto R1-E2E-EXP-…, «Exportar rascunho» e «Exportar conjunto oficial»; descarregar os dois .zip.
3. No fim: `docker compose down -v`, `make up`, `make seed-library` (o percurso aprova os blocos na BD).

## MDJ e CTE (.docx), oficial e rascunho

- [ ] Abrem no Word **sem** «O Word encontrou conteúdo ilegível» nem pedido de reparação.
- [ ] O Word pergunta se atualiza os campos (o índice): responder Sim. É esperado (`updateFields`), não é reparação.
- [ ] Estilos TUU: faixas de título de nível 1 (tabela de 1 célula), «Heading 2», «Estilo1», listas, legendas.
- [ ] Numeração dos títulos e das listas igual à do original de R1.
- [ ] Índice: depois de atualizar, lista as secções desta peça (não as de R1) com os números de página certos.
- [ ] Imagens e fórmulas (quedas de tensão, curto-circuito) no sítio e legíveis; «Imagens meramente ilustrativas».
- [ ] Tabelas IP/IK completas, sem células desalinhadas.
- [ ] Cabeçalho da 1.ª página: «TÉCNICO RESPONSÁVEL: <nome do perfil>», «DATA | REVISÃO:» sem data (ou a data que o
      técnico escreveu) e «R00»; cabeçalho das outras páginas e rodapé (Pág. x de y, TUU) como no original.
- [ ] Assinatura sem data nem assinatura.
- [ ] Ficheiro → Informações → Propriedades: autor e «último a alterar» = TUU, título «<CÓDIGO> · …», sem nomes de pessoas.
- [ ] Rascunho: «RASCUNHO — não aprovado» na diagonal em **todas** as páginas, incluindo a 1.ª.
- [ ] Oficial: nenhuma marca de água; nenhum «[falta: …]» nem «{{v:…}}» no texto (Ctrl+L).

## Ficha eletrotécnica (.xlsm)

- [ ] Abre no Excel sem pedido de reparação; o aviso de macros aparece (é um .xlsm) e as macros correm.
- [ ] Listas pendentes DGEG (descrição do imóvel, instalação, classificação, tipo de instalação, entrada…) funcionam.
- [ ] Formatação, células unidas, logótipo/controlos e área de impressão como no modelo DGEG.
- [ ] Valores da ficha-base nas células certas; R29 e I40/I42/I44 recalculados ao abrir.
- [ ] Bloco do técnico (nome, NIF, telefone, email, n.º DGEG) do perfil; M40 (data) vazia; sem assinatura.
- [ ] Rascunho: «RASCUNHO — não aprovado» no cabeçalho da pré-visualização de impressão.

## Identificação do projeto e Termo de responsabilidade (.docx)

- [ ] Abrem sem reparação; tabelas e caixas de seleção como no modelo DGEG.
- [ ] Campos preenchidos pela ficha-base e pelo perfil; «Instalação nova/existente» do Termo com o X certo.
- [ ] Sem data, sem assinatura; a declaração está lá, por assinar.
- [ ] Rascunho: marca de água em todas as páginas.

## Conjunto (.zip)

- [ ] Nomes: `<CÓDIGO>_MDJ_PE_ELE_V0.docx`, `…_CTE_…`, `…_FichaEletrotecnica_…xlsm`, `…_IdentificacaoProjeto_…docx`,
      `…_TermoResponsabilidade_…docx` e `manifesto.json`; rascunho com `_RASCUNHO-nao-aprovado`.
- [ ] `manifesto.json`: peças, revisões, quem aprovou, avisos ignorados com justificação, o que falta preencher à mão.
- [ ] Com «Incluir o PDF», os PDF abrem e coincidem com os .docx.

Anotar aqui o que falhar (ficheiro, página, o que se vê) e abrir uma tarefa.
