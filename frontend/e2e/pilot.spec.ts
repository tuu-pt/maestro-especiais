import { expect, test } from "@playwright/test";

import { expectNoSeriousA11yIssues, horizontalOverflow, mockApi, screenshot } from "./support";

const STEPS = [
  "Juntar e conferir os dados de partida",
  "Ficha eletrotécnica e ficha-base",
  "Escrever a MDJ",
  "Escrever o CTE",
  "Identificação, termo e ficha eletrotécnica",
  "Verificar a coerência entre peças",
  "Corrigir o que a revisão aponta",
  "Montar o conjunto final",
];
const KEYS = ["dados", "ficha", "mdj", "cte", "formularios", "verificacao", "correcoes", "conjunto"];

const PROJECT = {
  id: "p1",
  code: "R9",
  name: "Moradia",
  building_type: "Moradia unifamiliar",
  phase: "execucao",
  specialties: ["ELE"],
  public_procurement: false,
  status: "active",
  llm_allowed: true,
  created_at: "2026-10-09T08:00:00Z",
  files: [],
};

const PILOT = {
  project_id: "p1",
  code: "R9",
  typology: "habitação unifamiliar",
  steps: KEYS.map((step, i) => ({
    step,
    label: STEPS[i],
    seconds: [600, 900, 3000, 2400, 600, 1200, 0, 300][i],
    estimate_min: i < 6 ? [30 * (i + 1), 40 * (i + 1)] : null,
  })),
  seconds: 9000,
  estimate_seconds: 37800,
  reduction: 0.76,
  has_estimate: true,
  rounds_estimate: 2,
  errors_estimate: null,
  approvals: [
    {
      document: "MDJ",
      revision: "A",
      approved_at: "2026-10-09T10:00:00Z",
      groups: {
        identificacao: { found: 1, open: 0, ignored: 0 },
        potencia: { found: 0, open: 0, ignored: 0 },
        cabos: { found: 0, open: 0, ignored: 0 },
      },
      clean: true,
    },
  ],
  goal: { reduction: 0.78, time_ok: true, approved: true, coherent: true, met: true },
  notes_open: 1,
  notes_total: 1,
  baseline: null,
  notes: [
    {
      id: "n1",
      project_id: "p1",
      screen: "documentos",
      step: "cte",
      text: "O bloco da introdução repete a obra.",
      status: "open",
      created_by: "dev:redator",
      created_at: "2026-10-09T09:00:00Z",
      resolved_by: null,
      resolved_at: null,
    },
  ],
};

test.beforeEach(async ({ page }) => {
  await mockApi(page, { "/projects/p1": PROJECT, "/projects/p1/pilot": PILOT });
});

for (const scheme of ["light", "dark"] as const) {
  test(`pilot of a project: no serious accessibility issues (${scheme})`, async ({ page }, info) => {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto("/projetos/p1/piloto");
    await expect(page.getByRole("region", { name: "Tempo por passo" })).toBeVisible();
    await expect(page.getByText("Cumprida")).toBeVisible();
    await expectNoSeriousA11yIssues(page);
    await screenshot(page, info, `piloto-${scheme === "light" ? "claro" : "escuro"}`);
  });
}

test("the problem dialog is reachable by keyboard and closes with Escape", async ({ page }) => {
  await page.goto("/projetos/p1/piloto");
  await page.getByRole("button", { name: "Registar problema" }).click();
  const dialog = page.getByRole("dialog", { name: "Registar problema do piloto" });
  await expect(dialog.getByRole("textbox")).toBeFocused();
  await expectNoSeriousA11yIssues(page);
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("button", { name: "Registar problema" })).toBeFocused();
});

test.describe("phone width (400 px)", () => {
  test.use({ viewport: { width: 400, height: 860 } });

  test("pilot of a project: no horizontal scroll", async ({ page }, info) => {
    await page.goto("/projetos/p1/piloto");
    await expect(page.getByRole("region", { name: "Tempo por passo" })).toBeVisible();
    expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
    await screenshot(page, info, "piloto-telemovel");
  });
});
