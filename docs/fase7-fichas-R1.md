# Fase 7 · Equipamentos de R1 contra as fichas técnicas

Gerado por `make fichas-report` (backend/tests/test_equipment_r1_datasheets.py). As fichas
são as dos fabricantes em `data/fixtures/fichas-tecnicas/R1/` (`fichas.json` diz a origem de
cada uma). Para mostrar a verificação que uma biblioteca revista daria, o teste toma **todos
os parâmetros lidos como revistos e todos os requisitos do CTE como aprovados**: na
aplicação, isso é o curador que decide (D7). A tensão é só informação (não é requisito):
as fichas listam alimentações, gamas e correntes de relés.

32 equipamentos no CTE de R1 · 20 com ficha técnica · Sem requisitos: 14 · Sem ficha: 12 · Cumpre: 5 · Por confirmar: 1

## Equipamento a equipamento

| Secção | Equipamento | Ficha | Lido da ficha (pág.) | Exigido no CTE → resultado | Verificação |
|---|---|---|---|---|---|
| Entrada de Energia | Portinhola PBT Tri (Quitérios +32470) | — | — | Corrente de curto-circuito ≥ 25 kA → sem ficha; Resistência ao impacto (IK) ≥ IK10 → sem ficha; Índice de proteção (IP) ≥ IP55 → sem ficha | Sem ficha |
| Entrada de Energia | Caixa para contador trifásico (Quitérios +302) | — | — | Corrente de curto-circuito ≥ 25 kA → sem ficha; Resistência ao impacto (IK) ≥ IK10 → sem ficha; Índice de proteção (IP) ≥ IP55 → sem ficha | Sem ficha |
| Quadros Elétricos | Quadro Elétrico Geral (Quitérios +34929 CX QUADRO (5x24) 120md P200 INT) | quiterios_+34929_quadro.pdf · sem data | IK07 (1), IP54 (1), 79 W (1), 690 V (1), 400 V (1), 230 V (1) | Resistência ao impacto (IK) ≥ IK02 → cumpre (IK07); Índice de proteção (IP) ≥ IP30 → cumpre (IP54) | Cumpre |
| Quadros Elétricos | Quadro Parcial Piso 1 (Quitérios +344 CX QUADRO (3x20) 60md P125 INT) | quiterios_+344_quadro.pdf · sem data | IK07 (1), IP54 (1), 48,5 W (1), 690 V (1), 400 V (1), 230 V (1) | Resistência ao impacto (IK) ≥ IK02 → cumpre (IK07); Índice de proteção (IP) ≥ IP30 → cumpre (IP54) | Cumpre |
| Tubos tipo VDLH | Tubos tipo VDLH (JSL Tubo VD FLH) | jsl_tubo_VD_FLH.pdf · sem data | IK09 (1), IPX6 (1), IP6X (1), 1220 W (1) | — | Sem requisitos |
| Tubos tipo ERM | Tubos tipo ERM (JSL Tubo ERM) | jsl_tubo_ERM.pdf · sem data | IK09 (1), IP6X (1), IPX7 (1) | — | Sem requisitos |
| Tubos tipo PEAD | Tubos tipo PEAD (Multitubos Tubolex Normal (N)) | — | — | — | Sem ficha |
| Caixas | Caixas de aparelhagem fundas (JSL 317N) | jsl_caixa_317N_319N.pdf · sem data | — | — | Sem requisitos |
| Caixas | Caixas de aparelhagem fundas (JSL 406) | jsl_caixa_404_406_407_408.pdf · sem data | — | — | Sem requisitos |
| Caixas | Caixas de derivação (JSL 315) | jsl_caixa_315.pdf · sem data | IK05 (1), IP42 (1) | — | Sem requisitos |
| Caixas | Caixas de derivação estanques (JSL J80-M) | jsl_caixa_J80-M.pdf · 2020-01-03 | IK08 (1), IP55 (1), IP66 (1), 500 V (1) | — | Sem requisitos |
| Aparelhagem | Aparelhagem (EFAPEL SIZA) | — | — | — | Sem ficha |
| Interruptores e Tomadas | Interruptor unipolar (EFAPEL SIZA) | efapel_siza_interruptores.pdf · sem data | 250 V (1) | — | Sem requisitos |
| Interruptores e Tomadas | Comutador de escada simples (EFAPEL SIZA) | efapel_siza_interruptores.pdf · sem data | 250 V (1) | — | Sem requisitos |
| Interruptores e Tomadas | Tomada Schuko Lig (EFAPEL SIZA) | efapel_siza_tomadas.pdf · sem data | 127 V (2), 250 V (1) | Índice de proteção (IP) ≥ IP44 → a ficha não diz | Por confirmar |
| Interruptores e Tomadas | Tomada Estanque Schuko com obturador (EFAPEL Estanque 48) | efapel_estanque48.pdf · sem data | IP65 (1), 250 V (1) | — | Sem requisitos |
| Espelhos | Espelhos simples (EFAPEL SIZA) | efapel_siza_espelhos_dimensoes.pdf · sem data | — | — | Sem requisitos |
| Espelhos | Espelhos duplo (EFAPEL SIZA) | efapel_siza_espelhos_dimensoes.pdf · sem data | — | — | Sem requisitos |
| Espelhos | Espelhos quadruplo (EFAPEL SIZA) | efapel_siza_espelhos_dimensoes.pdf · sem data | — | — | Sem requisitos |
| Detetores de Movimento | Detetores de movimento de 360º (PERRY 1SP SP020) | perry_1SP_SP020.pdf · sem data | 360 º (1), 25 º (1), 14 m (1), 10 m (1), IP20 (1), 2000 W (1), 480 W (1), 23 W (1), 250 W (1), 7 W (1), 240 V (1), 230 V (1) | Ângulo de deteção ≥ 360 º → cumpre (360 º); Alcance de deteção ≥ 14 m → cumpre (14 m); Índice de proteção (IP) ≥ IP20 → cumpre (IP20) | Cumpre |
| Detetores de Movimento | Detetores de movimento de 180º (PERRY 1SP SP010) | perry_1SP_SP010.pdf · sem data | 180 º (1), 35 º (1), 70 º (1), 12 m (1), 65x88x95 (1), IP44 (1), 400 W (1), 23 W (1), 7 W (1), 220 W (1), 1000 W (1), 240 V (1), 230 V (1) | Ângulo de deteção ≥ 180 º → cumpre (180 º); Alcance de deteção ≥ 12 m → cumpre (12 m); Índice de proteção (IP) ≥ IP44 → cumpre (IP44) | Cumpre |
| Iluminação Normal | L1 · Downlight compacto para aplicação encastrada (Climar TALLES 30 RO IN Recessed) | — | — | — | Sem ficha |
| Iluminação Normal | L7 · Aplique de parede saliente (Tromilux 4004) | tromilux_4004_L7.pdf · sem data | 2700 K (1), 3000 K (1), 4000 K (1), 5000 K (1), 6500 K (1), 120 º (1), IK03 (1), IP20 (1), 186 lm (1), 300 lm (1), 10 W (1), 240 V (1) | — | Sem requisitos |
| Iluminação Normal | L8 · Candeeiro de parede (Indelague Aura) | — | — | — | Sem ficha |
| Iluminação Normal | L9 · Luminária de encastrar (Exporlux Dot TP EN) | — | — | — | Sem ficha |
| Iluminação Normal | L14 · Aplique de parede exterior (Tromilux 2525) | — | — | Resistência ao impacto (IK) ≥ IK10 → sem ficha; Índice de proteção (IP) ≥ IP65 → sem ficha; Potência = 1,5 W → sem ficha | Sem ficha |
| Iluminação Normal | L15 · Aplique de parede exterior (Tromilux 2522) | — | — | Resistência ao impacto (IK) ≥ IK10 → sem ficha; Índice de proteção (IP) ≥ IP65 → sem ficha; Potência = 5 W → sem ficha | Sem ficha |
| Videoporteiro | Videoporteiro (Hikvision DS-KV6113-WPE1(C) + DS-KABV6113-RS) | hikvision_DS-KV6113-WPE1C.pdf · sem data | 78 º (2), 131 º (2), 40 º (3), IP65 (1), 10 W (3), 30 V (3) | Ângulo de deteção ≥ 131 º → cumpre (131 º); Ângulo de deteção ≥ 78 º → cumpre (78 º); Índice de proteção (IP) ≥ IP65 → cumpre (IP65) | Cumpre |
| Videoporteiro | Videoporteiro (Hikvision DS-KH6320-LE1(B)) | hikvision_DS-KH6320-LE1B.pdf · sem data | 14 º (3), 122 º (3), 6 W (3), 12 V (3) | — | Sem requisitos |
| Iluminação Segurança | BS · Blocos de iluminação de emergência LED (Legrand X-Light 180) | — | — | Autonomia ≥ 1 h → sem ficha; Resistência ao impacto (IK) ≥ IK07 → sem ficha; Índice de proteção (IP) ≥ IP42 → sem ficha; Fluxo luminoso ≥ 100 lm → sem ficha | Sem ficha |
| Elétrodos de Terra | Elétrodos-250microm (INFOCONTROL 4001Q) | — | — | — | Sem ficha |
| Caixa de Visita com Ligador Amovível | Caixa de Visita com Ligador Amovível (INFOCONTROL 4013I) | — | — | — | Sem ficha |

## Sem ficha técnica (fichas.json)

- Quitérios +32470 (portinhola): descontinuado; atual +32474
- Quitérios +302 (caixa de contador): não encontrado
- Multitubos «Tubolex Normal (N)»: não existe com este nome
- Climar TALLES 30 RO IN Recessed (L1): só a pedido por email
- Indelague Aura (L8): site bloqueia acesso automático
- Exporlux Dot TP EN (L9): só brochura da família
- Tromilux 2525 (L14) e 2522 (L15): só declaração CE / manual
- INFOCONTROL 4001Q e 4013I: só catálogo de 2019
