/** The files step with every kind of file, mocked (invented values): layout, themes, 400 px. */

import { expect, test } from "@playwright/test";

import { expectNoSeriousA11yIssues, horizontalOverflow, mockApi, screenshot } from "./support";

const f = (id: string, kind: string, filename: string, over: object = {}) => ({
  id, kind, filename, content_type: null, size_bytes: 102400, checksum: "a".repeat(64),
  template_version: null, ingest_status: "done", ingest_message: "9 valores lidos",
  ingest_warnings: [], created_at: "2026-09-24T10:01:00Z", created_by: "dev:redator", ...over,
}); // prettier-ignore
const files = [
  f("1", "ficha_eletrotecnica", "Ficha eletrotécnica.xlsm", { ingest_message: "18 valores lidos (18 novos)" }),
  f("2", "calc_summary", "Tabela de Cálculo.xlsx", { ingest_message: "4 valores lidos (4 novos) · 20 troços" }),
  f("3", "calc_circuit", "09-Folha de Cálculo QEG-ATRIO.xls", {
    ingest_warnings: ["Célula proteccao!J9 vazia ou sem número."],
  }),
  f("4", "calc_circuit", "09-Folha de Cálculo ARM-QEG.xls", {
    ingest_status: "failed", ingest_message: "09-Folha ilegível ou corrompida.",
  }),
  f("5", "lpu", "LPU.xlsx", { ingest_message: "LPU: 170 artigos (34 associados, 136 por associar)" }),
  f("6", "drawing_pdf", "Peças desenhadas.pdf", { ingest_message: "28 páginas · índice com 27 folhas" }),
]; // prettier-ignore
const project = { id: "p1", code: "R9", name: "Biblioteca", building_type: null, phase: "execucao",
  specialties: ["ELE"], public_procurement: false, status: "active", created_at: "2026-09-24T10:00:00Z",
  created_by: "dev:redator", file_count: 6, ficha_status: "draft", open_conflicts: 0 }; // prettier-ignore

test.beforeEach(async ({ page }) => {
  await mockApi(page, { "/projects/p1": project, "/projects/p1/files": files, "/projects": [project] });
});

for (const scheme of ["light", "dark"] as const) {
  test(`files step with every reader: accessible in the ${scheme} theme`, async ({ page }, info) => {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto("/projetos/p1/ficheiros");
    await expect(page.getByRole("list", { name: "Resumo por tipo de ficheiro" })).toBeVisible();
    await expectNoSeriousA11yIssues(page);
    await screenshot(page, info, `ficheiros-${scheme === "light" ? "claro" : "escuro"}`);
  });
}

test("files step with every reader: fits a 400 px phone", async ({ page }, info) => {
  await page.setViewportSize({ width: 400, height: 900 });
  await page.goto("/projetos/p1/ficheiros");
  await expect(page.getByText("Lido com avisos")).toBeVisible();
  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
  await screenshot(page, info, "ficheiros-telemovel");
});
