/**
 * Phase 3 journey against the real stack (SPEC section 14): as Curador, open a proposed block,
 * look at its evidence from R1 and R2, approve it and find the decision in the block's history
 * and in the recent activity. Screenshots in light, dark and phone width.
 *
 * It approves one block in the development database, so it only runs when asked: `make up`,
 * `make seed-library`, then RUN_CURATOR_JOURNEY=1 npm run e2e (reset with docker compose down -v).
 * Each run approves the first adaptive block still proposed.
 */

import { expect, type Page, test } from "@playwright/test";

import { expectNoSeriousA11yIssues, horizontalOverflow, screenshot } from "./support";

test.skip(
  !process.env.RUN_CURATOR_JOURNEY,
  "aprova um bloco na BD de desenvolvimento: correr com RUN_CURATOR_JOURNEY=1, make up e make seed-library",
);

async function asCurator(page: Page) {
  await page.goto("/conhecimento?separador=blocos");
  await page.getByLabel("Utilizador de desenvolvimento").selectOption({ label: "Curador (desenvolvimento)" });
  await expect(page.getByRole("list", { name: "Blocos do MDJ" })).toBeVisible();
}

test("curator: open a block, see the evidence, approve it, find it in the history", async ({ page }, info) => {
  test.setTimeout(120_000);
  await asCurator(page);

  const list = page.getByRole("list", { name: "Blocos do MDJ" });
  const candidate = list.getByRole("button").filter({ hasText: "adaptativo" }).filter({ hasText: "Proposto" }).first();
  await expect(candidate, "falta um bloco adaptativo proposto: correr make seed-library").toBeVisible();
  await candidate.click();

  const article = page.getByRole("article");
  await expect(article.getByText("Parágrafos e evidência")).toBeVisible();
  const title = (await article.getByRole("heading", { level: 3 }).innerText()).trim();
  const evidence = article.getByLabel("Evidência lado a lado").first();
  await expect(evidence).toBeVisible();
  await expect(evidence.getByText(/^R[12]$/).first()).toBeVisible();
  await expectNoSeriousA11yIssues(page);

  await article.getByLabel("Nota (opcional, fica registada)").fill("Revisto no percurso de aceitação da Fase 3.");
  await article.getByRole("button", { name: "Aprovar bloco" }).click();
  await expect(article.getByText("Aprovado", { exact: true }).first()).toBeVisible();
  await expect(article.getByRole("button", { name: "Aprovar bloco" })).toBeDisabled();
  const history = article.getByRole("region", { name: "Histórico do bloco" });
  await expect(history.getByText(`Aprovou o bloco «${title}» (MDJ)`)).toBeVisible();
  await screenshot(page, info, "curador-bloco-aprovado-claro");

  await page.emulateMedia({ colorScheme: "dark" });
  await expectNoSeriousA11yIssues(page);
  await screenshot(page, info, "curador-bloco-aprovado-escuro");
  await page.emulateMedia({ colorScheme: "light" });

  await page.setViewportSize({ width: 400, height: 860 });
  await expect(article).toBeVisible();
  expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
  await screenshot(page, info, "curador-bloco-aprovado-telemovel");
  await page.setViewportSize({ width: 1280, height: 900 });

  // the decision is also in the audit (the recent activity), with who made it
  const activity = await page.request.get("/api/activity?limit=20", { headers: { "X-Dev-User": "curador" } });
  const events = (await activity.json()) as { description: string; actor_name: string }[];
  const event = events.find((e) => e.description === `Aprovou o bloco «${title}» (MDJ)`);
  expect(event?.actor_name).toBe("Curador (desenvolvimento)");
});

test("curator: a rule with an error is refused, with its position", async ({ page }) => {
  await asCurator(page);
  const list = page.getByRole("list", { name: "Blocos do MDJ" });
  await list.getByRole("button", { name: /INSTALAÇÃO FOTOVOLTAICA/ }).click();
  const article = page.getByRole("article", { name: "INSTALAÇÃO FOTOVOLTAICA" });
  await expect(article.getByText("sys.fv.present", { exact: true })).toBeVisible();

  await article.getByRole("button", { name: "Editar" }).click();
  const rule = article.getByRole("textbox", { name: "Regra de ativação" });
  await rule.fill("sys.fv");
  await article.getByLabel("Porquê (obrigatório, fica registado)").fill("Teste da validação da regra.");
  await article.getByRole("button", { name: "Guardar alterações" }).click();

  await expect(article.getByRole("alert")).toHaveText(/Falta a comparação depois de «sys.fv» .*\(posição 7\)/);
  await article.getByRole("button", { name: "Cancelar" }).click();
  await expect(article.getByText("sys.fv.present", { exact: true })).toBeVisible(); // nothing was saved
});
