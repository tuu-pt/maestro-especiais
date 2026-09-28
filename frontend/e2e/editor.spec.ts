/** Screen D · editor with an assembled MDJ (mock API): proposal and diff, both themes, a phone, axe. */

import { expect, type Page, test } from "@playwright/test";

import { confirmedFicha, forms, mdj, proposal, supplySection } from "../src/test/documents";
import { project } from "../src/test/fixtures";
import { expectNoSeriousA11yIssues, horizontalOverflow, mockApi, screenshot } from "./support";

async function open(page: Page, seccao = "s-supply") {
  await mockApi(page, {
    "/projects": [project()],
    "/projects/p1": project(),
    "/projects/p1/ficha": confirmedFicha(),
    "/projects/p1/documents": [mdj()],
    "/documents/d1": mdj(),
    "/projects/p1/forms": forms(),
    "/sections/s-supply/versions": [
      {
        ...proposal(),
        id: "v1",
        number: 1,
        status: "current",
        author_type: "system",
        content: supplySection().content,
      },
      proposal(),
    ],
    "/sections/s-fixed/versions": [],
    "/sections/s-pv/versions": [],
  });
  await page.goto(`/projetos/p1/documentos?doc=MDJ&seccao=${seccao}`);
  await expect(page.getByRole("heading", { level: 1, name: "Editor assistido" })).toBeVisible();
  await expect(page.getByRole("article")).toBeVisible();
}

test("sections, a proposal as a diff and the value from the ficha-base", async ({ page }) => {
  await open(page);
  const panel = page.getByRole("region", { name: "Proposta do agente" });
  await expect(panel.locator("ins")).toContainText("A entrada foi dimensionada");
  await expect(panel.getByRole("button", { name: "Aceitar proposta" })).toBeEnabled();
  await expect(page.locator('[data-value="ele.potencia_alimentar_kva"]')).toHaveText("34,5");
  await expect(page.getByText("Bloco não aprovado pelo curador", { exact: false })).toBeVisible();
});

for (const scheme of ["light", "dark"] as const) {
  test.describe(`${scheme} theme`, () => {
    test.use({ colorScheme: scheme });

    for (const seccao of ["s-supply", "s-fixed", "s-pv"]) {
      test(`${seccao}: no serious accessibility issues`, async ({ page }, info) => {
        await open(page, seccao);
        await expectNoSeriousA11yIssues(page);
        await screenshot(page, info, `editor-${seccao}-${scheme === "light" ? "claro" : "escuro"}`);
      });
    }
  });
}

test.describe("phone width (400 px)", () => {
  test.use({ viewport: { width: 400, height: 860 } });

  test("no horizontal scroll", async ({ page }, info) => {
    await open(page);
    expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
    await screenshot(page, info, "editor-telemovel");
  });
});
