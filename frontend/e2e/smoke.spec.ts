import { expect, test } from "@playwright/test";

test("home page opens in Portuguese with the service status card", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveTitle("Maestro Especiais");
  await expect(page.locator("html")).toHaveAttribute("lang", "pt-PT");
  await expect(page.getByRole("heading", { level: 1, name: "Maestro Especiais" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Estado dos serviços" })).toBeVisible();
});

test("is usable at 400 px wide without horizontal scroll", async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 800 });
  await page.goto("/");

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
