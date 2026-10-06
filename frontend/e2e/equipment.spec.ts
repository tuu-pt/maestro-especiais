/** Screens F and G · equipment (mock API): the check of each reference equipment against its
 * datasheet and the library of the curator; both themes, a phone, axe. */

import { expect, type Page, test } from "@playwright/test";

import { detail, luminaire, projectEquipment, slotDetail, summary } from "../src/test/equipment";
import { project } from "../src/test/fixtures";
import { expectNoSeriousA11yIssues, horizontalOverflow, mockApi, screenshot } from "./support";

const API = {
  "/projects": [project()],
  "/projects/p1": project(),
  "/projects/p1/equipment": projectEquipment(),
  "/project-equipment/s1": slotDetail(),
  "/project-equipment/s2": { ...luminaire, alternatives: [] },
  "/equipment": [summary(), summary({ id: "e2", name: "Aplique exterior", code: "L14", params_reviewed: 3 })],
  "/equipment/categories": [{ id: "portinhola", label: "Portinhola" }],
  "/equipment/params": [],
  "/equipment/e1": detail(),
};

async function openF(page: Page) {
  await mockApi(page, API);
  await page.goto("/projetos/p1/equipamentos");
  await expect(page.getByRole("heading", { level: 1, name: "Equipamentos e fichas técnicas" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Requisito do CTE contra a ficha do fabricante" })).toBeVisible();
}

async function openG(page: Page) {
  await mockApi(page, API);
  await page.goto("/conhecimento?separador=equipamentos&equipamento=e1");
  await expect(page.getByRole("region", { name: "Parâmetros da ficha técnica" })).toBeVisible();
}

test("each equipment against its datasheet, and the row chosen by keyboard", async ({ page }) => {
  await openF(page);
  await expect(page.getByText("IP44 < IP55").first()).toBeVisible();
  await page.getByRole("button", { name: "L14 · Aplique exterior" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { level: 3, name: "L14 · Aplique exterior" })).toBeVisible();
  await expect(page).toHaveURL(/slot=s2/);
});

for (const scheme of ["light", "dark"] as const) {
  test.describe(`${scheme} theme`, () => {
    test.use({ colorScheme: scheme });

    test("screen F: no serious accessibility issues", async ({ page }, info) => {
      await openF(page);
      await expectNoSeriousA11yIssues(page);
      await screenshot(page, info, `equipamentos-${scheme === "light" ? "claro" : "escuro"}`);
    });

    test("library of screen G: no serious accessibility issues", async ({ page }, info) => {
      await openG(page);
      await expectNoSeriousA11yIssues(page);
      await screenshot(page, info, `biblioteca-equipamentos-${scheme === "light" ? "claro" : "escuro"}`);
    });
  });
}

test.describe("phone width (400 px)", () => {
  test.use({ viewport: { width: 400, height: 860 } });

  test("no horizontal scroll", async ({ page }, info) => {
    await openF(page);
    expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
    await screenshot(page, info, "equipamentos-telemovel");
    await openG(page);
    expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
  });
});
