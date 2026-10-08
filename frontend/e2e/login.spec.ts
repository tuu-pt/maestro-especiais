import { expect, test } from "@playwright/test";

import { expectNoSeriousA11yIssues, horizontalOverflow, mockApi, screenshot } from "./support";

const SIGNED_OUT = { status: 401, body: { detail: "Sessão não iniciada." } };

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await page.route("**/api/me", (route) =>
    route.fulfill({ status: SIGNED_OUT.status, json: SIGNED_OUT.body }),
  );
});

test("whoever is not signed in lands on the login page", async ({ page }) => {
  await page.goto("/validacao");
  await expect(page).toHaveURL(/\/entrar\?volta=%2Fvalidacao$/);
  await expect(page.getByRole("heading", { level: 1, name: "Maestro Especiais" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Entrar" })).toBeVisible();
});

for (const scheme of ["light", "dark"] as const) {
  test(`login page: no serious accessibility issues (${scheme})`, async ({ page }, info) => {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto("/entrar");
    await expect(page.getByLabel("Email")).toBeVisible();
    await expectNoSeriousA11yIssues(page);
    await screenshot(page, info, `entrar-${scheme === "light" ? "claro" : "escuro"}`);
  });
}

test.describe("phone width (400 px)", () => {
  test.use({ viewport: { width: 400, height: 860 } });

  test("login page: no horizontal scroll", async ({ page }, info) => {
    await page.goto("/entrar");
    await expect(page.getByLabel("Password")).toBeVisible();
    expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
    await screenshot(page, info, "entrar-telemovel");
  });
});
