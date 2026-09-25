/** Screen G with proposals (mock API): dictionary and lexicon, the curator's controls, both themes and a phone. */

import { expect, type Page, test } from "@playwright/test";

import { expectNoSeriousA11yIssues, horizontalOverflow, mockApi, screenshot } from "./support";

const proposed = { status: "proposed", reviewed_by: null, reviewed_at: null, review_note: null };
const CURATOR = { id: "dev:curador", name: "Curador (desenvolvimento)", roles: [{ id: "curador", label: "Curador" }] };

const CABLES = {
  designations: [
    {
      id: "d1",
      canonical: "RZ1-K (AS)",
      aliases: [],
      kind: "cabo",
      flexible: true,
      occurrences: [
        {
          project_code: "R2",
          source: "Tabela",
          source_file: "08-Tabela de Calculo/Tabela.xlsx",
          locator: "QUADRO!linha 12",
          raw_text: "RZ1-K (AS) 5G10",
          geometry: "5G10",
        },
      ],
      ...proposed,
    },
    {
      id: "d2",
      canonical: "XZ1(frt,zh)",
      aliases: [],
      kind: "cabo",
      flexible: null,
      occurrences: [
        {
          project_code: "R2",
          source: "LPU",
          source_file: "10-LPU/LPU.xlsx",
          locator: "LPU!linha 40",
          raw_text: "XZ1(frt,zh) 5G10mm²",
          geometry: "5G10",
        },
      ],
      ...proposed,
    },
  ],
  equivalences: [
    {
      id: "e1",
      a: "RZ1-K (AS)",
      b: "XZ1(frt,zh)",
      reason: "No mesmo projeto, a mesma secção e o mesmo número de condutores aparecem com as duas designações.",
      evidence: [
        {
          project: "R2",
          geometry: "5G10",
          a: {
            source: "Tabela",
            file: "08-Tabela de Calculo/Tabela.xlsx",
            locator: "QUADRO!linha 12",
            raw_text: "RZ1-K (AS) 5G10",
          },
          b: { source: "LPU", file: "10-LPU/LPU.xlsx", locator: "LPU!linha 40", raw_text: "XZ1(frt,zh) 5G10mm²" },
        },
      ],
      ...proposed,
    },
  ],
};

const TYPOLOGIES = [
  {
    id: "t1",
    name: "moradia unifamiliar",
    evidence: [{ project: "R1", source: "Ficha eletrotécnica", locator: "F23", text: "Unifamiliar" }],
    terms: [
      {
        id: "x1",
        term: "apartamento",
        relation: "incompatible",
        evidence: [
          {
            project: "R1",
            source: "CTE",
            file: "04-CTE/CTE.docx",
            locator: "parágrafo 120",
            text: "…a alimentação de cada apartamento será feita a partir do…",
          },
        ],
        ...proposed,
      },
    ],
    ...proposed,
  },
];

const REGULATIONS = [
  {
    id: "g1",
    code: "rtiebt",
    title: "RTIEBT: Portaria n.º 949-A/2006, na redação atual",
    kind: "diploma",
    edition: null,
    issuer: "Governo",
    scope: "Regras Técnicas das Instalações Elétricas de Baixa Tensão.",
    status: null,
    citable: false,
    copyrighted: false,
    license_note: null,
    last_checked_at: null,
    review_status: "proposed",
    reviewed_by: null,
    reviewed_at: null,
    review_note: null,
    found_in: [
      {
        project: "R1",
        source: "MDJ",
        file: "MBERAL/2-PE/Editavel/MBERAL_MDJ_PE_ELE_V0.docx",
        locator: "parágrafo 44",
        text: "…deverão obedecer ao estipulado nas secções 521 e 801.5 da RTIEBT.",
      },
    ],
    found_count: 12,
  },
];

async function open(page: Page, tab?: string) {
  await mockApi(page, {
    "/me": CURATOR,
    "/knowledge/cables": CABLES,
    "/knowledge/typologies": TYPOLOGIES,
    "/knowledge/regulations": REGULATIONS,
  });
  await page.goto(tab ? `/conhecimento?separador=${tab}` : "/conhecimento");
  await expect(page.getByRole("heading", { level: 1, name: "Base de conhecimento" })).toBeVisible();
}

test("a curator sees the evidence and can approve or reject", async ({ page }) => {
  await open(page);
  await expect(page.getByText("RZ1-K (AS) 5G10").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Aprovar a equivalência RZ1-K (AS) ≈ XZ1(frt,zh)" })).toBeEnabled();

  await page.getByRole("tab", { name: "Léxico de tipologias" }).click();
  await expect(page.getByText(/cada apartamento/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Rejeitar o termo apartamento para moradia unifamiliar" }),
  ).toBeVisible();
});

const TEXT: Record<string, string> = { cabos: "XZ1(frt,zh)", lexico: "apartamento", corpus: "RTIEBT" };

for (const scheme of ["light", "dark"] as const) {
  test.describe(`${scheme} theme`, () => {
    test.use({ colorScheme: scheme });

    for (const tab of ["cabos", "lexico", "corpus"]) {
      test(`${tab}: no serious accessibility issues`, async ({ page }, info) => {
        await open(page, tab);
        await expect(page.getByRole("tabpanel")).toContainText(TEXT[tab]!);
        await expectNoSeriousA11yIssues(page);
        await screenshot(page, info, `conhecimento-${tab}-${scheme === "light" ? "claro" : "escuro"}`);
      });
    }
  });
}

test.describe("phone width (400 px)", () => {
  test.use({ viewport: { width: 400, height: 860 } });

  for (const tab of ["cabos", "lexico", "corpus"]) {
    test(`${tab}: no horizontal scroll`, async ({ page }, info) => {
      await open(page, tab);
      await expect(page.getByRole("tabpanel")).toContainText(TEXT[tab]!);
      expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
      await screenshot(page, info, `conhecimento-${tab}-telemovel`);
    });
  }
});
