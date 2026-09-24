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
    { name: "Peças desenhadas", values: [] },
  ],
  circuits: [
    { id: "c1", row_index: 3, section: "ENTRADA DE ENERGIA", origin: "Portinhola", destination: "Q.E.G.", kva: "200", ib_a: "50", in_a: "63", idn_ma: null, iz_a: "347.17", i2_a: "504", iz145_a: "503.4", cable_raw: "XZ1(frt,zh) 4x16", length_m: "25", vd_total_pct: "0.8", breaking_capacity_ka: "6", installation: "ENT", phases: 3, source_ref: "Tabela!linha 3", cal01: { ib_in_iz: "ok", i2_iz145: "fail" } },
  ],
  open_conflicts: 1,
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
