/**
 * Phase 2 acceptance journey with the full anonymized R2 set, against the real stack (SPEC 14):
 * create project → upload every file of R2 → see the new conflicts (09-Folhas, LPU, drawings)
 * → resolve one → link an MQT/LPU article by hand. Screenshots in light, dark and phone.
 *
 * Skipped while data/fixtures/R2 does not exist. It creates a project in the development
 * database, so it only runs when asked: `make up`, then RUN_R2_JOURNEY=1 npm run e2e.
 */

import { readdirSync, statSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

import { expectNoSeriousA11yIssues, horizontalOverflow, screenshot } from "./support";

const R2 = resolve(dirname(fileURLToPath(import.meta.url)), "../../data/fixtures/R2");

function allFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? allFiles(path) : [path];
  });
}

test.skip(!existsSync(R2), "data/fixtures/R2 não existe: anonimizar R2 para fechar a Fase 2");
test.skip(!process.env.RUN_R2_JOURNEY, "cria dados na BD de desenvolvimento: correr com RUN_R2_JOURNEY=1 e make up");

test("R2 full set: new conflicts, resolve one, link an article by hand", async ({ page }, info) => {
  test.setTimeout(240_000);
  const files = allFiles(R2);

  await page.goto("/projetos/novo");
  await page.getByLabel("Código do projeto").fill(`E2E-R2F-${Date.now()}`);
  await page.getByLabel("Designação").fill("Biblioteca municipal (R2 anonimizado, conjunto completo)");
  await page.getByRole("button", { name: "Seguinte: âmbito →" }).click();
  await page.getByRole("button", { name: "Criar projeto e carregar ficheiros →" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Ficheiros do projeto" })).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles(files);
  const list = page.getByRole("list", { name: "Ficheiros carregados" });
  await expect(list.getByRole("listitem")).toHaveCount(files.length, { timeout: 120_000 });
  await expect(list.getByText(/^(Na fila|A ler…|A carregar)$/)).toHaveCount(0, { timeout: 180_000 });
  const summary = page.getByRole("list", { name: "Resumo por tipo de ficheiro" });
  for (const kind of ["Ficha eletrotécnica", "Tabela de Cálculo", "09-Folhas de Cálculo", "MQT / LPU", "Peças desenhadas (PDF)"]) {
    await expect(summary.getByText(kind)).toBeVisible();
  }
  await expect(summary.getByText("Por carregar")).toHaveCount(0);
  await screenshot(page, info, "r2-completo-ficheiros");

  await page.getByRole("link", { name: "Ver a ficha do projeto →" }).click();
  await expect(page.getByRole("heading", { name: /^Conflitos por resolver \(\d+\)$/ })).toBeVisible();
  // New in Phase 2: a circuit conflict from a 09-Folha and C7 from the LPU (C6 is still there).
  const inConflict = page.getByRole("region", { name: "Portinhola → Q.E.G. · In: as fontes não coincidem" });
  await expect(inConflict).toBeVisible();
  await expect(page.getByRole("region", { name: "Requerente: as fontes não coincidem" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Potência a alimentar: as fontes não coincidem" })).toBeVisible();
  await expect(page.getByText("Índice e PDF coincidem")).toBeVisible();
  await expect(page.getByRole("heading", { name: "09-Folhas por associar (1)" })).toBeVisible();
  await screenshot(page, info, "r2-completo-conflitos-claro");

  // Resolve one: only a técnico responsável resolves (section 4).
  await page.getByLabel("Utilizador de desenvolvimento").selectOption({ label: "Técnico responsável (desenvolvimento)" });
  await inConflict.getByRole("button", { name: /315/ }).click();
  await inConflict.getByLabel("Justificação (fica registada)").fill("Confirmado na Tabela de Cálculo (315 A).");
  await inConflict.getByRole("button", { name: "Confirmar escolha" }).click();
  await expect(inConflict).toHaveCount(0);

  // Link an article that no rule recognized.
  const articles = page.getByRole("region", { name: "Tabela dos artigos do LPU" });
  await expect(page.getByRole("button", { name: /^Por associar \(\d+\)$/ })).toHaveAttribute("aria-pressed", "true");
  const firstSelect = articles.getByRole("combobox").first();
  const selectLabel = await firstSelect.getAttribute("aria-label");
  await firstSelect.selectOption({ label: "Distribuição · Cabos" });
  await page.getByRole("button", { name: /^Associados \(\d+\)$/ }).click();
  await expect(articles.getByLabel(selectLabel ?? "")).toHaveValue("ele.cabos");
  await expect(articles.getByText("Cabos · à mão")).toBeVisible();

  await expectNoSeriousA11yIssues(page);
  await screenshot(page, info, "r2-completo-ficha-claro");
  await page.emulateMedia({ colorScheme: "dark" });
  await expectNoSeriousA11yIssues(page);
  await screenshot(page, info, "r2-completo-ficha-escuro");
  await page.setViewportSize({ width: 400, height: 900 });
  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
  await screenshot(page, info, "r2-completo-ficha-telemovel");

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.getByRole("link", { name: "Revisão" }).click();
  await expect(page.getByText(/Resolveu o conflito do troço Portinhola → Q\.E\.G\./)).toBeVisible();
  await expect(page.getByText(/Associou o artigo .+ a «Cabos»/)).toBeVisible();
});
