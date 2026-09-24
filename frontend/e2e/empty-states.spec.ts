import { expect, test } from "@playwright/test";

import { expectNoSeriousA11yIssues, horizontalOverflow, mockApi, SCREENS, screenshot } from "./support";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("the application starts empty and offers to create a project", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Ainda não há projetos" })).toBeVisible();
  await page.getByRole("link", { name: "Criar projeto" }).click();
  await expect(page).toHaveURL(/\/projetos\/novo$/);
});

for (const [path, title] of SCREENS) {
  test(`${title}: empty state without invented data`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
    const body = await page.locator("main").innerText();
    expect(body).not.toMatch(/\d+\s?kVA/); // no values that did not come from a document
  });
}

for (const scheme of ["light", "dark"] as const) {
  test.describe(`${scheme} theme`, () => {
    test.use({ colorScheme: scheme });

    for (const [path, title] of SCREENS) {
      test(`${title}: no serious accessibility issues`, async ({ page }) => {
        await page.goto(path);
        await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
        await expectNoSeriousA11yIssues(page);
      });
    }

    test("screenshots of the empty dashboard, wizard and ficha", async ({ page }, info) => {
      for (const [path, name] of [["/", "painel"], ["/projetos/novo", "novo-projeto"], ["/ficha", "ficha"]]) {
        await page.goto(path);
        await expect(page.locator("h1")).toBeVisible();
        await screenshot(page, info, `${name}-${scheme === "light" ? "claro" : "escuro"}`);
      }
    });
  });
}

test.describe("phone width (400 px)", () => {
  test.use({ viewport: { width: 400, height: 860 } });

  for (const [path, title] of SCREENS) {
    test(`${title}: no horizontal scroll`, async ({ page }) => {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
      expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
    });
  }

  test("screenshots on the phone", async ({ page }, info) => {
    for (const [path, name] of [["/", "painel"], ["/projetos/novo", "novo-projeto"]]) {
      await page.goto(path);
      await expect(page.locator("h1")).toBeVisible();
      await screenshot(page, info, `${name}-telemovel`);
    }
  });
});

test("keyboard: every screen is reachable and the main action works with Enter", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Ainda não há projetos" })).toBeVisible();
  let reached = false;
  for (let i = 0; i < 40 && !reached; i++) {
    await page.keyboard.press("Tab");
    reached = await page.evaluate(() => document.activeElement?.textContent === "Criar projeto");
  }
  expect(reached).toBe(true);
  const outline = await page.evaluate(() => getComputedStyle(document.activeElement as Element).outlineStyle);
  expect(outline).not.toBe("none"); // visible focus
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/projetos\/novo$/);

  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Navegação principal" });
  for (const link of await nav.getByRole("link").all()) {
    await link.focus();
    await expect(link).toBeFocused();
  }
});
