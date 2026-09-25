/**
 * Phase 1 acceptance journey with the anonymized R2, against the real stack (SPEC section 14):
 * create project → upload → ficha → resolve the power conflict (C6) → confirm the revision.
 *
 * Skipped while data/fixtures/R2 does not exist. It creates a project in the development
 * database, so it only runs when asked: `make up`, then RUN_R2_JOURNEY=1 npm run e2e.
 */

import { existsSync, readdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

import { expectNoSeriousA11yIssues, horizontalOverflow, screenshot } from "./support";

// E2E_R2_DIR only to check this journey itself with synthetic files.
const R2 = process.env.E2E_R2_DIR ?? resolve(dirname(fileURLToPath(import.meta.url)), "../../data/fixtures/R2");

/**
 * The two Phase 1 sources of R2: the ficha eletrotécnica (.xlsm) and the Tabela de Cálculo. The
 * test picks them by file name; the app still detects every file by its content. The full set
 * (09-Folhas, LPU, drawings) is the Phase 2 journey, r2-full-set.spec.ts.
 */
function spreadsheets(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return spreadsheets(path);
    return /\.xlsm$/i.test(name) || /^Tabela.*\.xlsx$/i.test(name) ? [path] : [];
  });
}

test.skip(!existsSync(R2), "data/fixtures/R2 não existe: anonimizar R2 para fechar a Fase 1");
test.skip(!process.env.RUN_R2_JOURNEY, "cria dados na BD de desenvolvimento: correr com RUN_R2_JOURNEY=1 e make up");

test("R2: create, upload, resolve the power conflict and confirm", async ({ page }, info) => {
  test.setTimeout(120_000);
  const code = `E2E-R2-${Date.now()}`;

  await page.goto("/projetos/novo");
  await page.getByLabel("Código do projeto").fill(code);
  await page.getByLabel("Designação").fill("Biblioteca municipal (R2 anonimizado)");
  await page.getByRole("button", { name: "Seguinte: âmbito →" }).click();
  await page.getByRole("button", { name: "Criar projeto e carregar ficheiros →" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Ficheiros do projeto" })).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles(spreadsheets(R2));
  const files = page.getByRole("list", { name: "Ficheiros carregados" });
  await expect(files.getByText("Lido", { exact: true })).toHaveCount(2, { timeout: 60_000 });
  await expect(files.getByText(/^(Na fila|A ler…|A carregar)$/)).toHaveCount(0, { timeout: 60_000 });
  await expect(files.getByText("Não lido", { exact: true })).toHaveCount(0);

  await page.getByRole("link", { name: "Ver a ficha do projeto →" }).click();
  const conflict = page.getByRole("region", { name: "Potência a alimentar: as fontes não coincidem" });
  await expect(conflict).toBeVisible();
  const candidates = conflict.getByRole("group", { name: "Candidatos para Potência a alimentar" });
  await expect(candidates.getByRole("button", { name: /180 kVA/ })).toBeVisible();
  await expect(candidates.getByRole("button", { name: /200 kVA/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Confirmar revisão A" })).toBeDisabled();
  await screenshot(page, info, "r2-conflito-claro");

  // Only a técnico responsável resolves and confirms (section 4).
  await page.getByLabel("Utilizador de desenvolvimento").selectOption({ label: "Técnico responsável (desenvolvimento)" });
  await candidates.getByRole("button", { name: /200 kVA/ }).click();
  await conflict.getByLabel("Justificação (fica registada)").fill("CTE e Tabela de Cálculo indicam 200 kVA (caso C6).");
  await conflict.getByRole("button", { name: "Confirmar escolha" }).click();
  await expect(conflict).toHaveCount(0);

  // Any other divergence of R2 must be looked at by a person, not by this test.
  await expect(page.getByRole("region", { name: /as fontes não coincidem$/ })).toHaveCount(0);

  await page.getByRole("button", { name: "Confirmar revisão A" }).click();
  await expect(page.getByText("Confirmada", { exact: true })).toBeVisible();
  await expect(page.getByText("rev. A confirmada")).toBeVisible();
  await expectNoSeriousA11yIssues(page);
  await screenshot(page, info, "r2-confirmada-claro");

  await page.emulateMedia({ colorScheme: "dark" });
  await expectNoSeriousA11yIssues(page);
  await screenshot(page, info, "r2-confirmada-escuro");

  await page.setViewportSize({ width: 400, height: 860 });
  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
  await screenshot(page, info, "r2-confirmada-telemovel");

  // The confirmation is in the audit log of the project.
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.getByRole("link", { name: "Revisão" }).click();
  await expect(page.getByText("Confirmou a ficha-base rev. A")).toBeVisible();
  await expect(page.getByText(/Resolveu o conflito «Potência a alimentar»/)).toBeVisible();
});
