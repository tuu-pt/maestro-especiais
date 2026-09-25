/** Screen G · block library with a proposed block (mock API): both themes, a phone, accessibility. */

import { expect, type Page, test } from "@playwright/test";

import { expectNoSeriousA11yIssues, horizontalOverflow, mockApi, screenshot } from "./support";

const review = { status: "proposed", reviewed_by: null, reviewed_at: null, review_note: null };
const CURATOR = { id: "dev:curador", name: "Curador (desenvolvimento)", roles: [{ id: "curador", label: "Curador" }] };
const KEY = "ele.mdj.instalacao_de_alimentacao_distribuicao_e_medida_de_energia.alimentacao_de_energia";

const SUMMARY = {
  id: "b1",
  key: KEY,
  doc_type: "MDJ",
  kind: "block",
  level: 2,
  title: "Alimentação de Energia",
  order: 9,
  mode: "adaptive",
  activation_rule: "true",
  projects: ["R1", "R2"],
  required_keys: ["ele.potencia_alimentar_kva"],
  notes: [
    "Texto diferente em R1 e R2.",
    "Só em R1: os valores da ficha foram trocados por marcadores, com evidência de um só projeto.",
  ],
  version: 1,
  ...review,
};

const DETAIL = {
  ...SUMMARY,
  entries: [
    {
      mode: "fixed",
      project: "R1",
      units: { R1: [0], R2: [0] },
      text: "Alimentação de Energia",
      keys: [],
      single_source: false,
      note: null,
    },
    {
      mode: "adaptive",
      project: "R1",
      units: { R1: [1], R2: [1] },
      text: null,
      keys: [],
      single_source: false,
      note: "Texto diferente em R1 e R2.",
    },
    {
      mode: "parametric",
      project: "R1",
      units: { R1: [5] },
      text: "Prevê-se a instalação de uma potência elétrica de {{v:ele.potencia_alimentar_kva}} kVA, sendo uma instalação do tipo C.",
      keys: ["ele.potencia_alimentar_kva"],
      single_source: true,
      note: "Só em R1: os valores da ficha foram trocados por marcadores, com evidência de um só projeto.",
    },
  ],
  evidence: {
    R1: [
      { index: 0, kind: "paragraph", text: "Alimentação de Energia" },
      {
        index: 1,
        kind: "paragraph",
        text: "A entrada foi dimensionada de forma a garantir com eficácia a segurança e a flexibilidade de exploração.",
      },
      {
        index: 5,
        kind: "paragraph",
        text: "Prevê-se a instalação de uma potência elétrica de {{v:ele.potencia_alimentar_kva}} kVA, sendo uma instalação do tipo C.",
      },
    ],
    R2: [
      { index: 0, kind: "paragraph", text: "Alimentação de Energia" },
      {
        index: 1,
        kind: "paragraph",
        text: "A entrada de energia será mantida, poderá ter de se proceder ao aumento de potência de entrada.",
      },
    ],
  },
  labels: { "ele.potencia_alimentar_kva": "Potência a alimentar" },
  archive_refs: [`arc:R1:${KEY}`, `arc:R2:${KEY}`],
  equipment_slots: [],
};

async function open(page: Page) {
  await mockApi(page, {
    "/me": CURATOR,
    "/library/blocks": [SUMMARY],
    "/library/blocks/b1": DETAIL,
    "/library/blocks/b1/history": [],
  });
  await page.goto("/conhecimento?separador=blocos&bloco=b1");
  await expect(page.getByRole("article", { name: "Alimentação de Energia" })).toBeVisible();
}

test("a curator sees the paragraphs, the evidence and the actions", async ({ page }) => {
  await open(page);
  const article = page.getByRole("article", { name: "Alimentação de Energia" });
  await expect(article.locator("mark").first()).toHaveText("Potência a alimentar");
  await expect(article.getByText("A entrada de energia será mantida", { exact: false })).toBeVisible();
  await expect(article.getByRole("button", { name: "Aprovar bloco" })).toBeEnabled();
  await expect(article.getByRole("button", { name: "Rejeitar bloco" })).toBeEnabled();
});

for (const scheme of ["light", "dark"] as const) {
  test.describe(`${scheme} theme`, () => {
    test.use({ colorScheme: scheme });

    test("no serious accessibility issues", async ({ page }, info) => {
      await open(page);
      await expectNoSeriousA11yIssues(page);
      await screenshot(page, info, `biblioteca-${scheme === "light" ? "claro" : "escuro"}`);
    });
  });
}

test.describe("phone width (400 px)", () => {
  test.use({ viewport: { width: 400, height: 860 } });

  test("no horizontal scroll", async ({ page }, info) => {
    await open(page);
    expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
    await screenshot(page, info, "biblioteca-telemovel");
  });
});
