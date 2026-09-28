/** A validation of a project for the tests of screen E: made-up shapes, not project data. */

import type { MatrixRow, Validation, ValidationIssue } from "../api/types";

export const issue = (over: Partial<ValidationIssue> = {}): ValidationIssue => ({
  id: "i1",
  rule_id: "COE-01",
  rule_title: "Quantidades diferentes entre peças",
  severity: "critical",
  category: "coherence",
  category_label: "Coerência",
  location: { piece: "doc:cte", piece_name: "CTE (existente)" },
  message: "N.º de carregadores de veículos elétricos diferente da referência (5): CTE (existente) 6.",
  evidence: {
    reference: { label: "ficha-base", value: "5" },
    values: [
      { piece: "doc:mdj", piece_name: "MDJ (existente)", value: "5", differs: false, where: "Veículos, parágrafo 2" },
      { piece: "doc:cte", piece_name: "CTE (existente)", value: "6", differs: true, where: "Veículos, parágrafo 1" },
    ],
  },
  likely_reading: "Erro provável no CTE.",
  suggested_fix: null,
  actions: ["open_editor", "open_ficha", "ignore"],
  new: true,
  status: "open",
  ignored_reason: null,
  resolved_by: null,
  resolved_at: null,
  ...over,
});

export const warning = (): ValidationIssue =>
  issue({
    id: "i2",
    rule_id: "REF-03",
    rule_title: "Referência incompleta",
    severity: "warning",
    category: "references",
    category_label: "Referências",
    location: { piece: "doc:mdj", piece_name: "MDJ (existente)" },
    message: "MDJ (existente) · Canalizações: «secções da RTIEBT» sem o número da secção.",
    evidence: { excerpt: "…nas secções da RTIEBT." },
    likely_reading: null,
    actions: ["open_editor", "ignore"],
    new: false,
  });

export const personal = (): ValidationIssue =>
  issue({
    id: "i3",
    rule_id: "COE-04",
    message: "Dados do técnico diferentes (n.º de membro OET): CTE, MDJ vs Termo, Identificação.",
    evidence: {
      values: [
        { piece: "doc:mdj", piece_name: "MDJ (existente)", value: "•••", differs: false, where: "Assinatura" },
        { piece: "file:t", piece_name: "Termo", value: "•••", differs: false, where: "2. N.º OET" },
      ],
      masked: true,
    },
    likely_reading: "Confirmar com o perfil do técnico.",
  });

const row = (over: Partial<MatrixRow>): MatrixRow => ({
  label: "N.º de carregadores VE",
  unit: "",
  reference: "5",
  cells: {
    MDJ: { value: "5", differs: false, pieces: ["MDJ (existente)"] },
    CTE: { value: "6", differs: true, pieces: ["CTE (existente)"] },
  },
  reading: "Erro provável no CTE.",
  severity: "critical",
  state: "differs",
  ...over,
});

export const validation = (issues: ValidationIssue[] = [issue(), warning()]): Validation => ({
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
    totals: { critical: 1, warning: 1, info: 0 },
    pieces: [
      { ref: "doc:mdj", kind: "MDJ", origin: "existing", name: "MDJ (existente)", column: "MDJ", date: null, document_id: "d1", file_id: "f1" },
      { ref: "doc:cte", kind: "CTE", origin: "existing", name: "CTE (existente)", column: "CTE", date: null, document_id: "d2", file_id: "f2" },
    ],
  },
  issues,
  matrix: {
    reference: "ficha-base rev. A",
    columns: [
      { id: "MDJ", label: "MDJ" },
      { id: "CTE", label: "CTE" },
    ],
    rows: [
      row({}),
      row({ label: "Potência a alimentar", unit: "kVA", reference: "200", cells: { MDJ: { value: "200", differs: false, pieces: ["MDJ"] } }, reading: "Coerente", severity: null, state: "ok" }),
    ],
  },
  rules: [],
});
