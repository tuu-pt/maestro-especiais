/**
 * The densest screen, with a mocked ficha-base (invented values, test only): layout at 400 px,
 * both themes and accessibility. The real journey with R2 is in r2-journey.spec.ts.
 */

import { expect, test } from "@playwright/test";

import { expectNoSeriousA11yIssues, horizontalOverflow, mockApi, screenshot } from "./support";

const revision = { id: "r1", label: "A", status: "draft", confirmed_by: null, confirmed_at: null, created_at: "2026-09-24T10:00:00Z" };
const v = (key: string, label: string, value: unknown, extra: object = {}) => ({
  id: key, key, label, value, unit: null, masked: false, personal_data: false, status: "pending",
  source_type: "ficha_eletrotecnica", source_ref: "Ficha Eletrotecnica!C5", source_file: "FE.xlsm", conflict: null, ...extra,
});
const ficha = {
  revision,
  revisions: [revision],
  groups: [
    { name: "Identificação", values: [v("id.requerente.nome", "Requerente", "•••", { masked: true, personal_data: true }), v("id.local.concelho", "Concelho", "Concelho de Teste")] },
    { name: "Imóvel", values: [v("ele.tipo_utilizacao", "Tipo de utilização", "Habitação")] },
    {
      name: "Alimentação",
      values: [
        v("ele.potencia_alimentar_kva", "Potência a alimentar", null, {
          unit: "kVA",
          status: "conflict",
          conflict: {
            id: "k1",
            candidates: [
              { value: 180, source_type: "ficha_eletrotecnica", source_ref: "Ficha Eletrotecnica!R29", source_file: "FE.xlsm", file_date: "2026-09-24T10:01:00Z" },
              { value: 200, source_type: "calc", source_ref: "Tabela!linha 3", source_file: "Tabela de Calculo.xlsx", file_date: "2026-09-24T10:02:00Z" },
            ],
          },
        }),
      ],
    },
    {
      name: "Distribuição",
      values: [
        v("ele.quadros", "Quadros", ["Q.E.G.", "Q.P.ADMIN", "Q.P.ATRIO", "Q.P.CAFETARIA", "Q.P.REGIE", "Q.P.BIB.INFANT.", "Q.P.BIB.ADULTOS", "Q.P.REPROGRAFIA", "Q.AVAC", "Q.UPS 10kVA"], {
          source_type: "calc", source_ref: "Tabela de Cálculo · origens e destinos",
        }),
      ],
    },
    { name: "Sistemas", values: [] },
    { name: "Equipamentos", values: [] },
    {
      name: "Peças desenhadas",
      values: [
        v("pd.indice", "Índice das folhas", [{ codigo: "EL001", titulo: "ÍNDICE", data: "06/26", revisao: null }, { codigo: "EL002", titulo: "PISO 1 - DISTRIBUIÇÃO DE ENERGIA", data: "06/26", revisao: null }], { source_type: "drawing", source_ref: "PDF · pág. 1 · índice" }),
        v("pd.n_paginas_pdf", "Páginas do PDF", 1, { source_type: "drawing", source_ref: "PDF · número de páginas" }),
      ],
    },
  ],
  circuits: [
    { id: "c1", row_index: 3, section: "ENTRADA DE ENERGIA", origin: "Portinhola", destination: "Q.E.G.", kva: "200", ib_a: "50", in_a: "63", idn_ma: null, iz_a: "347.17", i2_a: "504", iz145_a: "503.4", cable_raw: "XZ1(frt,zh) 4x16", length_m: "25", vd_total_pct: "0.8", breaking_capacity_ka: "6", installation: "ENT", phases: 3, source_ref: "Tabela!linha 3", section_mm2: "185", vd_section_pct: "0.49", cal01: { ib_in_iz: "ok", i2_iz145: "fail" },
      conflicts: [{ id: "kc1", field: "in_a", label: "In", candidates: [
        { value: 315, source_type: "calc", source_ref: "Tabela!linha 3", source_file: "Tabela de Calculo.xlsx", file_date: null },
        { value: 250, source_type: "calc_sheet", source_ref: "09-Folha ARM-QEG · proteccao!E9", source_file: "09-Folha ARM-QEG.xls", file_date: null },
      ] }] },
    { id: "c2", row_index: 14, section: "EDIFÍCIO", origin: "Q.P.EXTERIOR", destination: "CVE 1", kva: "7.4", ib_a: "32.17", in_a: "40", idn_ma: "30", iz_a: "77.3", i2_a: "58", iz145_a: "112.09", cable_raw: "RV-K 3G10mm2", length_m: "30", vd_total_pct: "1.2", breaking_capacity_ka: "6", installation: "ENT", phases: 1, source_ref: "Tabela!linha 30", section_mm2: "10", vd_section_pct: "0.7", cal01: { ib_in_iz: "ok", i2_iz145: "ok" }, conflicts: [] },
  ],
  circuit_sheets: [
    { id: "s1", origin_hint: "ARM", destination_hint: "QEG", source_file: "09-Folha ARM-QEG.xls", template: "TUU_09", values: { in_a: { value: 250, ref: "proteccao!E9" } }, circuit_ids: ["c1"], link_status: "rule" },
    { id: "s2", origin_hint: "QPEXT", destination_hint: "CVE", source_file: "09-Folha QPEXT-CVE.xls", template: "TUU_09", values: {}, circuit_ids: [], link_status: "unlinked" },
  ],
  bom_items: [
    { id: "b1", variant: "lpu", source_ref: "LPU!linha 41", source_file: "LPU.xlsx", code: "1.8.1.1", level: 4, kind: "article", designation: "Q.E.G.", unit: "Un", quantity: "1", link_key: "ele.quadros", link_label: "Quadros", link_status: "rule", link_rule: "board" },
    { id: "b2", variant: "lpu", source_ref: "LPU!linha 26", source_file: "LPU.xlsx", code: "1.2.1.1", level: 4, kind: "article", designation: "Fornecimento e montagem de cabo XAV 4(1x185)mm² em caminho de cabos, incluindo acessórios", unit: "ml", quantity: "25", link_key: null, link_label: null, link_status: "unlinked", link_rule: null },
  ],
  bom_link_keys: [{ key: "ele.cabos", label: "Cabos", group: "Distribuição" }, { key: "ele.quadros", label: "Quadros", group: "Distribuição" }],
  drawings_check: { index_sheets: 2, pages: 1, missing_in_pdf: ["EL002"], not_in_index: [], matches: false },
  open_conflicts: 2,
  can_confirm: false,
  cal01_note: "Queda de tensão e poder de corte: a verificação fica disponível quando houver MDJ com os limites do projeto.",
};
const project = { id: "p1", code: "R9", name: "Moradia", building_type: null, phase: "execucao", specialties: ["ELE"], public_procurement: false, status: "active", created_at: "2026-09-24T10:00:00Z", created_by: "dev:redator", file_count: 2, ficha_status: "draft", open_conflicts: 1 };

test.beforeEach(async ({ page }) => {
  await mockApi(page, { "/projects/p1": project, "/projects/p1/ficha": ficha, "/projects": [project] });
});

for (const scheme of ["light", "dark"] as const) {
  test(`ficha with data: accessible in the ${scheme} theme`, async ({ page }, info) => {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto("/projetos/p1/ficha");
    await expect(page.getByRole("heading", { name: "Ficha-base · rev. A" })).toBeVisible();
    await expectNoSeriousA11yIssues(page);
    await screenshot(page, info, `ficha-com-dados-${scheme === "light" ? "claro" : "escuro"}`);
  });
}

for (const width of [1280, 400]) {
  test(`a long value wraps and leaves its label visible at ${width} px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/projetos/p1/ficha");
    const label = page.locator("dt", { hasText: "Quadros" });
    const value = page.locator("dd", { hasText: "Q.P.BIB.ADULTOS" });
    const [l, d] = [await label.boundingBox(), await value.boundingBox()];
    expect(l && d).toBeTruthy();
    expect(l!.width).toBeGreaterThan(50);
    expect(l!.x + l!.width).toBeLessThanOrEqual(d!.x + 1); // side by side, never on top
  });
}

test("ficha with data: fits a 400 px phone", async ({ page }, info) => {
  await page.setViewportSize({ width: 400, height: 860 });
  await page.goto("/projetos/p1/ficha");
  await expect(page.getByRole("heading", { name: "Ficha-base · rev. A" })).toBeVisible();
  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
  await screenshot(page, info, "ficha-com-dados-telemovel");
});
