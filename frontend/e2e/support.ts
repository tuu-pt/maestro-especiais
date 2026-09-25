/** Helpers for the Playwright tests: a mock API in the browser, empty by default. */

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, type TestInfo } from "@playwright/test";

const USERS = [
  { login: "redator", id: "dev:redator", name: "Redator (desenvolvimento)", roles: [{ id: "redator", label: "Redator" }] },
  {
    login: "tecnico",
    id: "dev:tecnico",
    name: "Técnico responsável (desenvolvimento)",
    roles: [
      { id: "redator", label: "Redator" },
      { id: "tecnico", label: "Técnico responsável" },
    ],
  },
];

export type Extra = Record<string, unknown>;

/** Serve /api from the test: empty application unless `extra` adds responses by path. */
export async function mockApi(page: Page, extra: Extra = {}): Promise<void> {
  // Only the API: a glob like **/api/** would also catch the Vite modules in /src/api/.
  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api/, "");
    const base: Extra = {
      "/me": USERS[0],
      "/dev/users": USERS,
      "/projects": [],
      "/activity": [],
      "/knowledge/cables": { designations: [], equivalences: [] },
      "/knowledge/typologies": [],
      "/library/blocks": [],
      "/health": { status: "ok", services: { database: { status: "ok" }, redis: { status: "ok" } } },
    };
    const body = path in extra ? extra[path] : base[path];
    if (path.endsWith("/events")) {
      return route.fulfill({ status: 200, contentType: "text/event-stream", body: "" });
    }
    if (body === undefined) return route.fulfill({ status: 404, json: { detail: "Não encontrado" } });
    return route.fulfill({ json: body });
  });
}

export const SCREENS: [path: string, title: string][] = [
  ["/", "Painel"],
  ["/projetos/novo", "Novo projeto"],
  ["/ficha", "Ficha do projeto"],
  ["/documentos", "Editor assistido"],
  ["/validacao", "Validação"],
  ["/equipamentos", "Equipamentos e fichas técnicas"],
  ["/revisao", "Revisão e exportação"],
  ["/conhecimento", "Base de conhecimento"],
  ["/definicoes", "Definições"],
];

export async function horizontalOverflow(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

/** axe-core with the WCAG 2.1 A/AA rules; serious and critical findings fail the test. */
export async function expectNoSeriousA11yIssues(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const serious = results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.help} (${v.nodes.map((n) => n.target.join(" ")).join(", ")})`);
  expect(serious, serious.join("\n")).toEqual([]);
}

export async function screenshot(page: Page, info: TestInfo, name: string): Promise<void> {
  const path = info.outputPath(`${name}.png`);
  await page.screenshot({ path, fullPage: true });
  await info.attach(name, { path, contentType: "image/png" });
}
