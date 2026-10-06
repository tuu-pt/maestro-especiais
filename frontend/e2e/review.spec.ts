/** Screen H · review and export (mock API): the approval card, the diff, the exports; both themes,
 * a phone, axe. The journey against the stack is r1-export-journey.spec.ts. */

import { expect, type Page, test } from "@playwright/test";

import { mdj } from "../src/test/documents";
import { project } from "../src/test/fixtures";
import { approval, approvedWithHistory, diff, exportDone } from "../src/test/review";
import { expectNoSeriousA11yIssues, horizontalOverflow, mockApi, screenshot } from "./support";

async function open(page: Page, approved: boolean) {
  await mockApi(page, {
    "/projects": [project()],
    "/projects/p1": project(),
    "/projects/p1/documents": [mdj()],
    "/documents/d1": mdj(),
    "/documents/d1/approval": approved ? approvedWithHistory() : approval(),
    "/documents/d1/diff": diff(),
    "/projects/p1/exports": [exportDone(), exportDone({ id: "e0", status: "failed", message: "A exportação falhou." })],
    "/projects/p1/audit": [],
    "/sections/s-supply/versions": [],
  });
  await page.goto("/projetos/p1/revisao");
  await expect(page.getByRole("heading", { level: 1, name: "Revisão e exportação" })).toBeVisible();
  await expect(page.getByRole("list", { name: "Condições para aprovar" })).toBeVisible();
}

test("the conditions say why and where; the official set waits for the approval", async ({ page }) => {
  await open(page, false);
  const conditions = page.getByRole("list", { name: "Condições para aprovar" });
  await expect(conditions.getByText("2 blocos por aprovar", { exact: false })).toBeVisible();
  await expect(conditions.getByRole("link", { name: "Resolver" }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Aprovar MDJ" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Exportar conjunto oficial" })).toBeDisabled();
});

for (const scheme of ["light", "dark"] as const) {
  test.describe(`${scheme} theme`, () => {
    test.use({ colorScheme: scheme });

    for (const approved of [false, true]) {
      test(`${approved ? "approved, with its diff" : "in review"}: no serious accessibility issues`, async ({
        page,
      }, info) => {
        await open(page, approved);
        if (approved) {
          await expect(page.getByRole("region", { name: "Diferenças em «Alimentação de Energia»" })).toBeVisible();
        }
        await expectNoSeriousA11yIssues(page);
        const name = `revisao-${approved ? "aprovada" : "em-revisao"}-${scheme === "light" ? "claro" : "escuro"}`;
        await screenshot(page, info, name);
      });
    }
  });
}

test.describe("phone width (400 px)", () => {
  test.use({ viewport: { width: 400, height: 860 } });

  test("no horizontal scroll", async ({ page }, info) => {
    await open(page, true);
    expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
    await screenshot(page, info, "revisao-telemovel");
  });
});
