# Fase 5 · Anexo C: os casos reais de R1 e R2 na validação

Gerado por `make anexo-c-report` (`app/validation/annex_c.py`, a partir do teste `tests/test_validation_annex_c.py`): R1 e R2 carregados como auditoria (ficha eletrotécnica, Tabela de Cálculo, MQT/LPU, PDF das peças desenhadas e a MDJ, o CTE, a identificação e o termo feitos à mão), ficha-base confirmada como no projeto aprovado e validação corrida. Não mostra valores pessoais: a evidência sai mascarada (•••).

**14 de 14 casos detetados com a leitura provável esperada.**

| Caso | Projeto | O que acontece | Regra | Resultado | Leitura obtida | Evidência |
|---|---|---|---|---|---|---|
| C1 | R1 | MDJ indica fios H07V-K; CTE e Tabela de Cálculo indicam H07V-U | COE-06 | Detetado | Erro provável na MDJ. | family: H07V-K; compared_with: H07V-U |
| C2 | R1 | CTE (videoporteiro): «ecrã na entrada de cada apartamento» numa moradia | TIP-01 | Detetado | Texto herdado de outro projeto. | «…l, tecnológica e estética, um ecrã tátil na entrada de cada apartamento com características de design elegante e minimalista e o mó…» |
| C3 | R1 | N.º de membro OET do técnico diferente entre MDJ/CTE e identificação/termo | COE-04 | Detetado | Confirmar com o perfil do técnico. | perfil do técnico: ••• · CTE (existente): •••; MDJ (existente): •••; Termo: •••; Identificação: ••• |
| C4 | R1 | Índice das peças desenhadas com 17 folhas; PDF com 16 páginas | DES-01 | Detetado | Folha em falta no PDF ou índice desatualizado. | pages: 16; matches: False; index_sheets: 17 |
| C5 | R1 (contratação pública) | Videoporteiro com marca sem «ou equivalente»; referência repetida | CCP-01 + TXT-01 | Detetado | — | «Modelo: Hikvision DS-KV6113-WPE1(C) + DS-KABV6113-RS» · «Comutador de escada simples – EFAPEL – SIZA Ref. 45070 S ou Ref. 45071 S, ou 450…» |
| C6 | R2 | Potência: ficha eletrotécnica 180 kVA; CTE e Tabela 200 kVA; MDJ sem valor | COE-05 + CNT-01 | Detetado | Erro provável na ficha eletrotécnica. | ficha-base: 200 · CTE (existente): 200 kVA; Ficha eletrotécnica: 180 ≠; Tabela de Cálculo: 200 · value: a potência a alimentar; reference: 200 |
| C7 | R2 | Ficha eletrotécnica com outro requerente, «Escritório», rua e freguesia vazias | COE-04 + TIP-01 | Detetado | Ficha eletrotécnica reaproveitada de outro projeto (2 campos de identificação diferentes). | ficha-base: ••• · CTE (existente): •••; MDJ (existente): •••; Peças desenhadas: •••; LPU: •••; Ficha eletrotécnica: ••• ≠ · value: Escritório |
| C8 | R2 | Carregadores VE: MDJ e Tabela 5; CTE 3 pedestais com 2 carregadores (6) | COE-01 | Detetado | Erro provável no CTE. | ficha-base sem valor: Tabela de Cálculo (fonte da ficha-base): 5 · CTE (existente): 6 ≠; MDJ (existente): 5; LPU: 5; Tabela de Cálculo: 5 |
| C9 | R2 | Cabos: FXZ1 (MDJ/CTE), RZ1-K (AS) (Tabela), XZ1(frt,zh) (LPU) | COE-06 | Detetado | Pedir equivalência ao curador. | family: FXZ1; compared_with: RV-K · family: XZ1(frt,zh); equivalence: proposed; compared_with: RZ1-K (AS) |
| C10 | R2 | Troço Portinhola → Q.E.G.: I2 = 504 A e 1,45·Iz = 503,4 A | CAL-01 | Detetado | Confirmar na folha de cálculo. | I2 = 504 A; 1,45·Iz = 503,44 A |
| C11 | R2 | «Segundo a secção das RTIEBT» e «secções da RTIEBT» sem número | REF-03 | Detetado | — | «Segundo a secção das RTIEBT, o espaço a estudar é uma Biblioteca. O edifício da Bibliot…» · «…ma de caminho de cabos e deverão obedecer ao estipulado nas secções da RTIEBT.» |
| C12 | R2 | Troços enterrados (ENT) e MDJ sem bloco de canalizações enterradas | COE-03 | Detetado | Bloco em falta na MDJ. | rule: any circuit.installation == "ENT" or any bom.designation ~ "abertura e tapamento de vala"; block: Canalizações Enterradas; section: canalizacoes.canalizacoes_enterradas |
| C13 | R2 | Parágrafos da MDJ com quebras de linha a meio de frase | TXT-01 | Detetado | — | «…a os circuitos, será em função da secção dos condutores, dos ⏎ tipos de circuito (monofásico, trifásico com neutro e trifás…» |
| C14 | R1 | Duas entradas quase iguais sobre normas portuguesas na legislação da MDJ | TXT-01 | Detetado | — | «Normas portuguesas aplicáveis, as recomendações técnicas da IEC e demais regulam…» |

## Casos de controlo (não podem gerar alertas)

| Controlo | Alertas |
|---|---|
| Potência (34,5 kVA) igual na ficha eletrotécnica, identificação, MDJ e Tabela | nenhum |
| N.º de quadros (6) igual na MDJ, CTE, MQT e Tabela | nenhum |

## Outros alertas reais

Alertas que a validação encontra em R1 e R2 para além do Anexo C, para a equipa rever (a leitura provável é a da regra). Os de informação estão contados, não listados.

### R1 (5 críticos e avisos; 9 de informação)

| Regra | Severidade | Alerta | Leitura |
|---|---|---|---|
| COE-04 | Crítico | Identificação diferente (rua): CTE (existente), MDJ (existente) não coincide(m) com a ficha-base. | Várias peças divergem da ficha-base (CTE (existente), MDJ (existente)): confirmar a ficha-base e cada peça. |
| COE-06 | Crítico | Designação de cabos diferente: MQT indica H07V-K e a Tabela de Cálculo indica H07V-U (fio flexível vs rígido: cabos diferentes). | Erro provável no MQT. |
| COE-03 | Aviso | CTE (existente): falta o bloco «Iluminação Segurança», e o projeto tem o sistema correspondente. | Bloco em falta no CTE. |
| COE-03 | Aviso | MDJ (existente): falta o bloco «Iluminação de Segurança», e o projeto tem o sistema correspondente. | Bloco em falta na MDJ. |
| COE-06 | Aviso | Designação de cabos diferente: CTE (existente) indica XV; a Tabela de Cálculo indica RV-K (sem equivalência no dicionário). | Pedir equivalência ao curador. |

### R2 (25 críticos e avisos; 6 de informação)

| Regra | Severidade | Alerta | Leitura |
|---|---|---|---|
| COE-01 | Crítico | N.º de quadros elétricos diferente da referência (14): CTE (existente) 16; LPU 16. | Várias peças divergem da ficha-base (CTE (existente), LPU): confirmar a ficha-base e cada peça. |
| COE-04 | Crítico | Identificação diferente (designação da obra): Peças desenhadas não coincide(m) com a ficha-base. | Erro provável nas peças desenhadas. |
| CAL-01 | Aviso | Troço Q.E.G. → Q.P.ADMIN: poder de corte 3 kA abaixo do mínimo de 6 kA da MDJ. | Confirmar na folha de cálculo. |
| CAL-01 | Aviso | Troço Q.E.G. → Q.P.CAFETARIA: poder de corte 3 kA abaixo do mínimo de 6 kA da MDJ. | Confirmar na folha de cálculo. |
| CAL-01 | Aviso | Troço Q.E.G. → Q.P.REGIE: poder de corte 3 kA abaixo do mínimo de 6 kA da MDJ. | Confirmar na folha de cálculo. |
| CAL-01 | Aviso | Troço Q.E.G. → Q.P.BIB.INFANT.: poder de corte 3 kA abaixo do mínimo de 6 kA da MDJ. | Confirmar na folha de cálculo. |
| CAL-01 | Aviso | Troço Q.E.G. → Q.P.BIB.ADULTOS: poder de corte 3 kA abaixo do mínimo de 6 kA da MDJ. | Confirmar na folha de cálculo. |
| CAL-01 | Aviso | Troço Q.E.G. → Q.P.REPROGRAFIA: poder de corte 3 kA abaixo do mínimo de 6 kA da MDJ. | Confirmar na folha de cálculo. |
| CAL-01 | Aviso | Troço Q.E.G. → UPS 10kVA: poder de corte 3 kA abaixo do mínimo de 6 kA da MDJ. | Confirmar na folha de cálculo. |
| CAL-01 | Aviso | Troço Q.UPS 10kVA → Q.P.UPS.P-1: poder de corte 3 kA abaixo do mínimo de 6 kA da MDJ. | Confirmar na folha de cálculo. |
| CAL-01 | Aviso | Troço Q.P.EXTERIOR → CVE 1: poder de corte 3 kA abaixo do mínimo de 6 kA da MDJ. | Confirmar na folha de cálculo. |
| CAL-01 | Aviso | Troço Q.P.EXTERIOR → CVE 2: poder de corte 3 kA abaixo do mínimo de 6 kA da MDJ. | Confirmar na folha de cálculo. |
| CAL-01 | Aviso | Troço Q.P.EXTERIOR → CVE 3: poder de corte 3 kA abaixo do mínimo de 6 kA da MDJ. | Confirmar na folha de cálculo. |
| CAL-01 | Aviso | Troço Q.P.EXTERIOR → CVE 4: poder de corte 3 kA abaixo do mínimo de 6 kA da MDJ. | Confirmar na folha de cálculo. |
| CAL-01 | Aviso | Troço Q.P.EXTERIOR → CVE 5: poder de corte 3 kA abaixo do mínimo de 6 kA da MDJ. | Confirmar na folha de cálculo. |
| CNT-01 | Aviso | CTE (existente): falta o bloco obrigatório «Espelhos». | Bloco em falta no CTE. |
| CNT-01 | Aviso | MDJ (existente): falta o bloco obrigatório «Distribuição de Energia». | Bloco em falta na MDJ. |
| COE-03 | Aviso | MDJ (existente): falta o bloco «Iluminação de Segurança», e o projeto tem o sistema correspondente. | Bloco em falta na MDJ. |
| COE-06 | Aviso | Designação de cabos diferente: CTE (existente) indica XV; a Tabela de Cálculo indica RV-K, RZ1-K (AS), XAV (sem equivalência no dicionário). | Pedir equivalência ao curador. |
| COE-06 | Aviso | Designação de cabos diferente: LPU indica SZ1(frt,zh); a Tabela de Cálculo indica RV-K, RZ1-K (AS), XAV (sem equivalência no dicionário). | Pedir equivalência ao curador. |
| COE-06 | Aviso | Designação de cabos diferente: LPU indica XZ1(frs,zh); a Tabela de Cálculo indica RV-K, RZ1-K (AS), XAV (há uma equivalência proposta, por aprovar). | Pedir equivalência ao curador. |
| REF-01 | Aviso | CTE (existente) · Sistema fotovoltaico: «Decreto-Lei n.º162/2019» não está no corpus. | Documento por acrescentar ao corpus: pedir ao curador. |
| REF-01 | Aviso | CTE (existente) · Sistema fotovoltaico: «Decreto de Lei n.º 226/2005» não está no corpus. | Documento por acrescentar ao corpus: pedir ao curador. |
| REF-01 | Aviso | CTE (existente) · Sistema de Alarme e Deteção de Incêndio (SADI): «EN54» não está no corpus. | Documento por acrescentar ao corpus: pedir ao curador. |
| REF-03 | Aviso | CTE (existente) · Canalizações: «secções das RTIEBT» sem o número da secção. | — |

## Regras sem caso no Anexo C

| Regra | Coberta por |
|---|---|
| REF-01 | texto do agente com fonte fora do corpus (tests/test_validation_engine.py) e citações do texto fora do corpus (aparecem em R2 como «outros alertas») |
| REF-02 | documento revogado (tests/test_validation_rules.py) e documentos por confirmar pelo curador (informação, em R1 e R2) |
| NUM-01 | número fora de marcador no texto do agente (tests/test_validation_engine.py) |
| COE-02 | ficheiro com data posterior à ficha-base (tests/test_validation_rules.py) |

EQP-01 a EQP-03 são da Fase 7.
