/** Screen E · Validação (mock API): issues, evidence, matrix, review gate; themes, phone, a11y. */

import { expect, type Page, test } from "@playwright/test";

import { expectNoSeriousA11yIssues, horizontalOverflow, mockApi, screenshot } from "./support";

const PROJECT = {
  id: "p1",
  code: "AUD",
  name: "Auditoria",
  building_type: "Biblioteca",
  phase: "execucao",
  specialties: ["ELE"],
  public_procurement: false,
  status: "active",
  created_at: "2026-09-28T09:00:00Z",
  created_by: "dev:redator",
  file_count: 6,
  ficha_status: "confirmed",
  open_conflicts: 0,
  validation: { status: "done", finished_at: "2026-09-28T10:00:05Z", open_critical: 2, new_critical: 2, warning: 1 },
};
const FICHA = {
  revision: null,
  revisions: [{ id: "rev-a", label: "A", status: "confirmed", confirmed_by: "dev:tecnico", confirmed_at: "2026-09-28T10:00:00Z", created_at: "2026-09-28T09:00:00Z" }],
  groups: [],
  circuits: [],
  circuit_sheets: [],
  bom_items: [],
  bom_link_keys: [],
  drawings_check: null,
  open_conflicts: 0,
  can_confirm: false,
  cal01_note: "",
};
const DOCUMENT = { id: "d1", project_id: "p1", type: "CTE", origin: "existing", source_file_id: "f1", status: "draft", ficha_revision: "A", created_at: "2026-09-28T09:30:00Z", counts: { sections: 50 }, sections: null };
const PIECES = [
  { ref: "doc:mdj", kind: "MDJ", origin: "existing", name: "MDJ (existente)", column: "MDJ", date: null, document_id: "d0", file_id: "f0" },
  { ref: "doc:cte", kind: "CTE", origin: "existing", name: "CTE (existente)", column: "CTE", date: null, document_id: "d1", file_id: "f1" },
  { ref: "file:fe", kind: "FICHA_ELE", origin: "file", name: "Ficha eletrotécnica", column: "FICHA_ELE", date: null, document_id: null, file_id: "f2" },
];
const base = { suggested_fix: null, new: true, status: "open", ignored_reason: null, resolved_by: null, resolved_at: null };
const ISSUES = [
  {
    ...base,
    id: "i1",
    rule_id: "COE-05",
    rule_title: "Potência diferente entre peças",
    severity: "critical",
    category: "coherence",
    category_label: "Coerência",
    location: { piece: "file:fe", piece_name: "Ficha eletrotécnica" },
    message: "Potência a alimentar diferente da ficha-base (200 kVA): Ficha eletrotécnica 180 kVA.",
    evidence: {
      reference: { label: "ficha-base", value: "200" },
      values: [
        { piece: "file:fe", piece_name: "Ficha eletrotécnica", value: "180", differs: true, where: "Ficha Eletrotecnica!P29" },
        { piece: "doc:cte", piece_name: "CTE (existente)", value: "200 kVA", differs: false, where: "Entrada de Energia, parágrafo 2" },
      ],
    },
    likely_reading: "Erro provável na ficha eletrotécnica.",
    actions: ["open_editor", "open_ficha", "ignore"],
  },
  {
    ...base,
    id: "i2",
    rule_id: "COE-04",
    rule_title: "Identificação diferente entre peças",
    severity: "critical",
    category: "coherence",
    category_label: "Coerência",
    location: { piece: "file:fe", piece_name: "Ficha eletrotécnica" },
    message: "Identificação diferente (requerente): Ficha eletrotécnica não coincide(m) com a ficha-base.",
    evidence: {
      reference: { label: "ficha-base", value: "•••" },
      values: [{ piece: "file:fe", piece_name: "Ficha eletrotécnica", value: "•••", differs: true, where: "Ficha Eletrotecnica!C5" }],
      masked: true,
    },
    likely_reading: "Ficha eletrotécnica reaproveitada de outro projeto (2 campos de identificação diferentes).",
    actions: ["open_editor", "open_ficha", "ignore"],
  },
  {
    ...base,
    id: "i3",
    new: false,
    rule_id: "REF-03",
    rule_title: "Referência incompleta",
    severity: "warning",
    category: "references",
    category_label: "Referências",
    location: { piece: "doc:mdj", piece_name: "MDJ (existente)", section_title: "Canalizações" },
    message: "MDJ (existente) · Canalizações: «secções da RTIEBT» sem o número da secção.",
    evidence: { excerpt: "…deverão obedecer ao estipulado nas secções da RTIEBT." },
    likely_reading: null,
    actions: ["open_editor", "ignore"],
  },
];
const cell = (value: string, differs = false) => ({ value, differs, pieces: [] });
const VALIDATION = {
  ready: true,
  current: null,
  run: {
    id: "r1",
    status: "done",
    trigger: "full",
    message: null,
    created_at: "2026-09-28T10:00:00Z",
    started_at: "2026-09-28T10:00:01Z",
    finished_at: "2026-09-28T10:00:05Z",
    totals: {},
    pieces: PIECES,
  },
  issues: ISSUES,
  matrix: {
    reference: "ficha-base rev. A",
    columns: [
      { id: "MDJ", label: "MDJ" },
      { id: "CTE", label: "CTE" },
      { id: "MQT_LPU", label: "MQT/LPU" },
      { id: "FICHA_ELE", label: "Ficha ELE" },
      { id: "IDENT_TERMO", label: "Identificação/Termo" },
      { id: "CALC", label: "Tabela de Cálculo" },
      { id: "DRAWINGS", label: "Desenhos" },
    ],
    rows: [
      { label: "Requerente", unit: "", reference: "•••", cells: { MDJ: cell("•••"), FICHA_ELE: cell("•••", true) }, reading: "Ficha eletrotécnica reaproveitada de outro projeto (2 campos de identificação diferentes).", severity: "critical", state: "differs" },
      { label: "Potência a alimentar", unit: "kVA", reference: "200", cells: { CTE: cell("200"), FICHA_ELE: cell("180", true), CALC: cell("200") }, reading: "Erro provável na ficha eletrotécnica.", severity: "critical", state: "differs" },
      { label: "N.º de quadros", unit: "", reference: "14", cells: { CALC: cell("14") }, reading: "Coerente", severity: null, state: "ok" },
      { label: "Cabos principais", unit: "", reference: "RV-K, RZ1-K (AS), XAV", cells: { MDJ: cell("FXZ1", true), CALC: cell("RV-K / RZ1-K (AS) / XAV") }, reading: "Pedir equivalência ao curador.", severity: "warning", state: "differs" },
    ],
  },
  rules: [],
};

async function open(page: Page) {
  await mockApi(page, {
    "/projects": [PROJECT],
    "/projects/p1": PROJECT,
    "/projects/p1/ficha": FICHA,
    "/projects/p1/documents": [DOCUMENT],
    "/projects/p1/validation": VALIDATION,
  });
  await page.goto("/projetos/p1/validacao");
  await expect(page.getByRole("list", { name: "Alertas da validação" })).toBeVisible();
  await page.getByText("Potência a alimentar diferente da ficha-base").click();
}

test("issues with evidence, the likely reading and the review gate", async ({ page }) => {
  await open(page);
  await expect(page.getByText("Erro provável na ficha eletrotécnica.").first()).toBeVisible();
  await expect(page.getByText("2 alertas críticos abertos: as peças não podem ser enviadas para revisão.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Enviar as peças para revisão" })).toBeDisabled();
  await expect(page.getByRole("region", { name: "Matriz de coerência do projeto" })).toBeVisible();
});

for (const scheme of ["light", "dark"] as const) {
  test.describe(`${scheme} theme`, () => {
    test.use({ colorScheme: scheme });

    test("no serious accessibility issues", async ({ page }, info) => {
      await open(page);
      await expectNoSeriousA11yIssues(page);
      await screenshot(page, info, `validacao-${scheme === "light" ? "claro" : "escuro"}`);
    });
  });
}

test.describe("phone width (400 px)", () => {
  test.use({ viewport: { width: 400, height: 860 } });

  test("no horizontal scroll", async ({ page }, info) => {
    await open(page);
    expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
    await screenshot(page, info, "validacao-telemovel");
  });
});

test("the dashboard shows the new critical issues", async ({ page }) => {
  await mockApi(page, { "/projects": [PROJECT] });
  await page.goto("/");
  const alert = page.getByRole("link", { name: /2 críticos/ });
  await expect(alert).toHaveAttribute("href", "/projetos/p1/validacao");
  await expect(alert.getByText("2 novos")).toBeVisible();
});
